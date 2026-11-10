"""Tournament check: score simulated stage distributions against past seasons."""

import json
import math
import subprocess
from datetime import UTC, datetime

from uclpred.backtest import PARAMS_PATH, REPORT_PATH, _md_table, merge_report
from uclpred.config import EXPORT, PROCESSED, ROOT, SEASONS
from uclpred.export import run_export
from uclpred.teams import TeamResolver

STAGES = ["out", "po", "r16", "qf", "sf", "final", "winner"]
STAGE_OF = {
    "PLAYOFFS": "po",
    "LAST_16": "r16",
    "QUARTER_FINALS": "qf",
    "SEMI_FINALS": "sf",
    "FINAL": "final",
}
SIGMAS = [0, 40, 70, 100]
MODELS = ["elo-dc-v1", "elo-dc-v2"]
SEASON_LIST = ["2024-25", "2025-26"]
EPS = 1e-6
SIGMA_TOL = 0.01
SIGMA_DEFAULT = 70
SECTION = "Tournament check"
EXPECTED_COUNTS = {"out": 12, "po": 8, "r16": 8, "qf": 4, "sf": 2, "final": 1, "winner": 1}


def _tid(team: dict, resolver, team_country) -> str:
    return resolver.resolve(team_country[team["id"]], team["name"])


def _sides(m: dict, resolver, team_country):
    return _tid(m["homeTeam"], resolver, team_country), _tid(m["awayTeam"], resolver, team_country)


def actual_outcomes(
    fd_matches: list[dict], resolver, team_country, expected: dict[str, int] | None = EXPECTED_COUNTS
) -> dict[str, str]:
    """Team id -> highest stage reached, for every league-phase team.

    Raises ValueError if a knockout participant is not a league-phase team or if
    the stage counts differ from `expected` (36 teams; None skips the count check)."""
    rank = {s: i for i, s in enumerate(STAGES)}
    out: dict[str, str] = {}
    for m in fd_matches:
        if m.get("stage") == "LEAGUE_STAGE":
            for t in _sides(m, resolver, team_country):
                out.setdefault(t, "out")
    winner = None
    for m in fd_matches:
        stage = STAGE_OF.get(m.get("stage"))
        if stage is None:
            continue
        sides = _sides(m, resolver, team_country)
        for t in sides:
            if t not in out:
                raise ValueError(f"knockout participant {t!r} ({stage}) is not a league-phase team")
            if rank[stage] > rank[out[t]]:
                out[t] = stage
        if stage == "final":
            w = (m.get("score") or {}).get("winner")
            if w in ("HOME_TEAM", "AWAY_TEAM"):
                winner = sides[0] if w == "HOME_TEAM" else sides[1]
    if winner is not None:
        out[winner] = "winner"
    if expected is not None:
        counts = {st: sum(1 for v in out.values() if v == st) for st in STAGES}
        if len(out) != sum(expected.values()) or counts != expected:
            raise ValueError(f"unexpected stage counts {counts} for {len(out)} teams; want {expected}")
    return out


def actual_top8(fd_matches: list[dict], resolver, team_country) -> set[str]:
    """Teams that played the LAST_16 without playing the PLAYOFFS (direct top 8)."""
    po, l16 = set(), set()
    for m in fd_matches:
        if m.get("stage") == "PLAYOFFS":
            po.update(_sides(m, resolver, team_country))
        elif m.get("stage") == "LAST_16":
            l16.update(_sides(m, resolver, team_country))
    return l16 - po


def stage_distribution(chances_team: dict) -> dict[str, float]:
    """Probability of finishing exactly at each stage."""
    r = chances_team["reach"]
    top8 = chances_team["top8"]
    d = {
        "out": chances_team["out"],
        "po": r["po"] - (r["r16"] - top8),
        "r16": r["r16"] - r["qf"],
        "qf": r["qf"] - r["sf"],
        "sf": r["sf"] - r["final"],
        "final": r["final"] - r["winner"],
        "winner": r["winner"],
    }
    assert all(v > -1e-6 for v in d.values()), f"negative stage probability: {d}"
    d = {k: max(v, 0.0) for k, v in d.items()}
    total = sum(d.values())
    assert abs(total - 1) < 1e-6, f"stage distribution sums to {total}"
    if abs(total - 1) > 1e-9:
        d = {k: v / total for k, v in d.items()}
    return d


def score_tournament(chances, actual: dict[str, str], top8_ids: set[str]) -> dict:
    """Score one simulated season. `chances` is a list of per-team dicts or a
    {teamId: dict} mapping; `top8_ids` the teams that actually finished top 8."""
    by_id = (
        {c["teamId"]: c for c in chances} if isinstance(chances, list) else dict(chances)
    )
    ll, b8, b24 = [], [], []
    for tid, stage in actual.items():
        c = by_id[tid]
        p = stage_distribution(c)[stage]
        ll.append(-math.log(max(p, EPS)))
        b8.append((c["top8"] - (1.0 if tid in top8_ids else 0.0)) ** 2)
        b24.append((c["top24"] - (0.0 if stage == "out" else 1.0)) ** 2)
    n = len(actual)
    return {
        "stage_log_loss": sum(ll) / n,
        "brier_top8": sum(b8) / n,
        "brier_top24": sum(b24) / n,
        "max_title_share": max(c["reach"]["winner"] for c in by_id.values()),
    }


def choose_sigma(means: dict[int, float]) -> int:
    """Lowest mean log loss; 70 when the four means lie within SIGMA_TOL."""
    if max(means.values()) - min(means.values()) <= SIGMA_TOL:
        return SIGMA_DEFAULT
    return min(means, key=lambda s: (means[s], s))


def _run_sim(season: str, model: str, sigma: int, runs: int) -> str:
    rel = f"data/export/bt/{season}/{model}"
    out = f"{rel}/chances_s{sigma}.json"
    subprocess.run(
        ["pnpm", "--filter", "@uclpred/sim", "cli", "--", "--input", rel, "--sigma", str(sigma),
         "--out", out, "--runs", str(runs), "--seed", "1"],
        cwd=ROOT, check=True,
    )  # fmt: skip
    return out


def run_tournament_check(runs: int = 50000) -> dict:
    resolver = TeamResolver()
    truth = {}
    for season in SEASON_LIST:
        y = SEASONS[season]["fd_year"]
        fd = json.loads((PROCESSED / f"cl_{y}_fd.json").read_text())
        teams = json.loads((PROCESSED / f"cl_{y}_teams.json").read_text())
        tc = {t["id"]: t["area"]["code"] for t in teams}
        truth[season] = (
            actual_outcomes(fd, resolver, tc),
            actual_top8(fd, resolver, tc),
        )
    rows = []
    for season in SEASON_LIST:
        actual, top8 = truth[season]
        for model in MODELS:
            # fresh export so inputs match current data and model_params.json
            run_export(
                as_of=SEASONS[season]["preseason_as_of"],
                out=EXPORT / "bt" / season / model,
                season=season,
                model_name=model,
            )
            for sigma in SIGMAS:
                _run_sim(season, model, sigma, runs)
                path = EXPORT / "bt" / season / model / f"chances_s{sigma}.json"
                chances = json.loads(path.read_text())["chances"]
                rows.append({"season": season, "model": model, "sigma": sigma,
                             **score_tournament(chances, actual, top8)})  # fmt: skip

    def mean(model, sigma, key):
        v = [r[key] for r in rows if r["model"] == model and r["sigma"] == sigma]
        return sum(v) / len(v)

    keys = ["stage_log_loss", "brier_top8", "brier_top24", "max_title_share"]
    v2_means = {s: mean("elo-dc-v2", s, "stage_log_loss") for s in SIGMAS}
    chosen = choose_sigma(v2_means)
    spread = max(v2_means.values()) - min(v2_means.values())
    v1_ll = mean("elo-dc-v1", 0, "stage_log_loss")
    v2_ll = v2_means[chosen]

    params = json.loads(PARAMS_PATH.read_text())
    params["elo-dc-v2"]["rating_sigma"] = chosen
    PARAMS_PATH.write_text(json.dumps(params, indent=2) + "\n")

    table = [{"season": r["season"], "model": r["model"], "sigma": r["sigma"],
              **{k: r[k] for k in keys}} for r in rows]  # fmt: skip
    for model in MODELS:
        for s in SIGMAS:
            table.append({"season": "mean", "model": model, "sigma": s,
                          **{k: mean(model, s, k) for k in keys}})  # fmt: skip
    import pandas as pd

    f4 = "{:.4f}"
    md = _md_table(pd.DataFrame(table), {k: f4 for k in keys})
    gate = "PASS" if v2_ll <= v1_ll else "FAIL"
    body = (
        f"Past seasons {', '.join(SEASON_LIST)}, preseason exports, {runs:,} runs, seed 1. "
        "stage_log_loss is the mean over the 36 teams of -log P(actual stage), floored at "
        "1e-6; brier_top8 scores the direct top-8 flag (played the Round of 16 without "
        "the play-offs); brier_top24 scores 'not out'; max_title_share is the largest "
        "title probability.\n\n" + md
        + f"\n\nChosen rating_sigma for elo-dc-v2: **{chosen}**. Rule: lowest mean "
        f"stage_log_loss over both seasons among {SIGMAS}; if the max-min spread of the "
        f"four means is at most {SIGMA_TOL}, choose {SIGMA_DEFAULT}. Observed spread "
        f"{spread:.4f} ({', '.join(f'{s}: {v:.4f}' for s, v in v2_means.items())}).\n\n"
        f"Gate 3 comparison (mean stage_log_loss over both seasons): v2 at sigma {chosen} = "
        f"{v2_ll:.4f}, v1 at sigma 0 = {v1_ll:.4f}; v2 <= v1: **{gate}**."
    )
    existing = REPORT_PATH.read_text() if REPORT_PATH.exists() else None
    intro = "Elo v2 calibration."
    if existing and "\n" in existing:
        # keep the existing intro paragraph untouched
        head = existing.split("\n## ", 1)[0]
        intro = head.split("\n", 1)[1].strip() if "\n" in head else intro
    stale = ("`uclpred tournament-check`", datetime.now(UTC).date().isoformat())
    REPORT_PATH.write_text(merge_report(existing, intro, [(SECTION, body)], stale=stale))
    print(md)
    print(f"chosen sigma {chosen}; gate3 v2 {v2_ll:.4f} vs v1 {v1_ll:.4f} ({gate})")
    return {"rows": rows, "chosen": chosen, "v1": v1_ll, "v2": v2_ll}
