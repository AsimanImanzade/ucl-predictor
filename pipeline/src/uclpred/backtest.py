"""Walk-forward backtest engine and paired bootstrap of the RPS difference."""

import itertools
import json
import re
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from uclpred.config import REFERENCE, REPORTS
from uclpred.elo import EloResult, run_elo
from uclpred.elo_v2 import EloV2Params, run_elo_v2
from uclpred.models.baseline import fit_baseline
from uclpred.models.metrics import brier, calibration_table, league_gap, log_loss, rps
from uclpred.models.score_matrix import outcome_probs

PARAMS_PATH = REFERENCE / "model_params.json"
REPORT_PATH = REPORTS / "calibration.md"
GRID_CSV_PATH = REPORTS / "backtest_grid.csv"
GATE_FROM = "2019-20"
GATE_TO = "2025-26"  # cap so live 2026-27 matches cannot move the gate number
TUNING_SEASONS = ["2019-20", "2020-21", "2021-22"]
REPORT_SEASONS = ["2022-23", "2023-24", "2024-25", "2025-26"]
HOME_ADV = 60.0
V1_ALPHA = 0.005
CORNER = {"k": 32.0, "k_euro": 3.0, "g": 1.0}
GRID = {
    "k": [16.0, 20.0, 24.0],
    "k_euro": [1.0, 1.5, 2.0],
    "g": [0.5, 0.7, 0.9],
    "alpha": [0.0005, 0.002, 0.005],
}
TIE_TOL = 0.0005

PRED_COLS = ["match_id", "season", "p_home", "p_draw", "p_away", "outcome"]


def monthly_checkpoints(dates: pd.Series) -> list[pd.Timestamp]:
    """00:00 UTC on the 1st of each month, from the month of min(dates) to the
    month after max(dates), inclusive."""
    d = pd.to_datetime(pd.Series(dates), utc=True)
    first = pd.Timestamp(d.min().year, d.min().month, 1, tz="UTC")
    last = pd.Timestamp(d.max().year, d.max().month, 1, tz="UTC") + pd.DateOffset(months=1)
    return list(pd.date_range(first, last, freq="MS", tz="UTC"))


def walk_forward(
    matches: pd.DataFrame, elo: EloResult, seasons: list[str], alpha: float
) -> pd.DataFrame:
    ev = matches[
        (matches["status"] == "FINISHED")
        & matches["competition"].str.startswith("uefa.")
        & matches["season"].isin(seasons)
    ]
    if ev.empty:
        return pd.DataFrame(columns=PRED_COLS)
    cps = monthly_checkpoints(ev["date"])
    rows = []
    for lo, hi in itertools.pairwise(cps):
        win = ev[(ev["date"] >= lo) & (ev["date"] < hi)]
        if win.empty:
            continue
        model = fit_baseline(matches, elo, as_of=lo, alpha=alpha)
        for r in win.itertuples(index=False):
            ph, pd_, pa = outcome_probs(
                model.predict_match(r.home_id, r.away_id, neutral=bool(r.neutral))
            )
            hg, ag = int(r.home_goals), int(r.away_goals)
            rows.append({
                "match_id": r.match_id, "season": r.season, "date": r.date,
                "p_home": ph, "p_draw": pd_, "p_away": pa,
                "outcome": 0 if hg > ag else 1 if hg == ag else 2,
            })  # fmt: skip
    out = pd.DataFrame(rows).sort_values(["date", "match_id"], kind="stable")
    return out[PRED_COLS].reset_index(drop=True)


def _arrays(preds: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    return preds[["p_home", "p_draw", "p_away"]].to_numpy(float), preds["outcome"].to_numpy(int)


def score(preds: pd.DataFrame) -> dict:
    p, y = _arrays(preds)
    return {"rps": rps(p, y), "log_loss": log_loss(p, y), "brier": brier(p, y), "n": len(preds)}


def _per_match_rps(probs: np.ndarray, outcomes: np.ndarray) -> np.ndarray:
    probs = np.asarray(probs, dtype=float)
    obs = np.zeros_like(probs)
    obs[np.arange(len(probs)), np.asarray(outcomes, dtype=int)] = 1.0
    diff = np.cumsum(probs, axis=1) - np.cumsum(obs, axis=1)
    return 0.5 * (diff[:, :2] ** 2).sum(axis=1)


def bootstrap_delta_rps(
    a: pd.DataFrame, b: pd.DataFrame, n_boot: int = 1000, seed: int = 1
) -> tuple[float, float, float]:
    """(mean, lo, hi) of rps(b) - rps(a) per match; 95% percentile CI over
    resamples of match ids. Raises ValueError if the match_id sets differ."""
    sa, sb = set(a["match_id"]), set(b["match_id"])
    if sa != sb or len(a) != len(sa) or len(b) != len(sb):
        raise ValueError(
            f"match_id sets differ: a has {len(sa)} unique ({len(a)} rows), "
            f"b has {len(sb)} unique ({len(b)} rows), "
            f"{len(sa - sb)} only in a, {len(sb - sa)} only in b"
        )
    a = a.set_index("match_id").sort_index()
    b = b.set_index("match_id").sort_index()
    delta = _per_match_rps(*_arrays(b)) - _per_match_rps(*_arrays(a))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(delta), size=(n_boot, len(delta)))
    means = delta[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(delta.mean()), float(lo), float(hi)


def run_grid(matches: pd.DataFrame, tuning_seasons: list[str], grid: dict) -> pd.DataFrame:
    """One row per (k, k_euro, g, alpha). Elo v2 and the league gaps are computed
    once per Elo-parameter set and shared across its alpha rows.

    league_gap is the gate scope (GATE_FROM..GATE_TO); league_gap_tuning is the
    same restricted to the tuning seasons (diagnostic)."""
    rows = []
    elo_sets = list(itertools.product(grid["k"], grid["k_euro"], grid["g"]))
    for i, (k, k_euro, g) in enumerate(elo_sets, 1):
        print(f"[grid {i}/{len(elo_sets)}] k={k} k_euro={k_euro} g={g}", flush=True)
        elo = run_elo_v2(matches, EloV2Params(k=k, k_euro=k_euro, g=g, home_adv=HOME_ADV))
        gap, _ = league_gap(matches, elo.pre, HOME_ADV, from_season=GATE_FROM, to_season=GATE_TO)
        gap_t, _ = league_gap(
            matches, elo.pre, HOME_ADV, from_season=min(tuning_seasons),
            to_season=max(tuning_seasons),
        )  # fmt: skip
        for alpha in grid["alpha"]:
            sc = score(walk_forward(matches, elo, tuning_seasons, alpha))
            rows.append({
                "k": k, "k_euro": k_euro, "g": g, "alpha": alpha,
                "rps": sc["rps"], "log_loss": sc["log_loss"], "brier": sc["brier"],
                "league_gap": gap, "league_gap_tuning": gap_t,
            })  # fmt: skip
    return pd.DataFrame(rows)


def tie_candidates(grid_df: pd.DataFrame) -> pd.DataFrame:
    """Rows within TIE_TOL of the best RPS."""
    return grid_df[grid_df["rps"] <= grid_df["rps"].min() + TIE_TOL]


def select_params(grid_df: pd.DataFrame, gap_col: str = "league_gap") -> dict:
    """Lowest RPS wins; rows within TIE_TOL of the best go to the smaller
    |gap|; remaining ties break on rps, k, k_euro, g, alpha."""
    cand = tie_candidates(grid_df).copy()
    cand["_abs_gap"] = cand[gap_col].abs()
    cand = cand.sort_values(["_abs_gap", "rps", "k", "k_euro", "g", "alpha"], kind="stable")
    r = cand.iloc[0]
    return {
        "k": float(r["k"]), "k_euro": float(r["k_euro"]), "g": float(r["g"]),
        "home_adv": HOME_ADV, "alpha": float(r["alpha"]),
        "rps": float(r["rps"]), "log_loss": float(r["log_loss"]),
        "brier": float(r["brier"]), "league_gap": float(r["league_gap"]),
    }  # fmt: skip


def load_model_params() -> dict:
    return json.loads(PARAMS_PATH.read_text())


def _md_table(df: pd.DataFrame, fmt: dict[str, str] | None = None) -> str:
    fmt = fmt or {}
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in df.itertuples(index=False):
        out.append("| " + " | ".join(fmt.get(c, "{}").format(v) for c, v in zip(cols, r)) + " |")
    return "\n".join(out)


SECTION_ORDER = [
    "Gate verdict",
    "Tournament check",
    "Grid (top 10)",
    "Chosen parameters",
    "Report seasons: v1 vs v2",
    "Calibration (v2)",
    "League gap",
    "Sensitivity (outside the pre-registered selection)",
]
STALE_RE = re.compile(r"(?m)^> ⚠️ Stale:.*\n\n?")


def _title(block: str) -> str:
    return block[3:].split("\n", 1)[0].strip()


def _mark_stale(block: str, tool: str, date: str) -> str:
    head, _, rest = block.partition("\n")
    rest = STALE_RE.sub("", rest.lstrip("\n"))
    line = f"> ⚠️ Stale: {tool} re-ran on {date}; numbers below may no longer match."
    return f"{head}\n\n{line}\n\n{rest}"


def merge_report(
    existing: str | None,
    intro: str,
    sections: list[tuple[str, str]],
    stale: tuple[str, str] | None = None,
) -> str:
    """Rebuild the report: title, intro and our own `## ` sections plus any other
    `## ` section already in `existing`, emitted in SECTION_ORDER (unknown
    sections after, in their existing order). With `stale=(tool, date)` a
    warning line is put at the top of an existing Gate verdict section."""
    own = {t for t, _ in sections}
    blocks = [f"## {t}\n\n{b.strip()}\n" for t, b in sections]
    if existing:
        for block in re.split(r"(?m)^(?=## )", existing):
            if block.startswith("## ") and _title(block) not in own:
                blocks.append(block.rstrip() + "\n")
    rank = {t: i for i, t in enumerate(SECTION_ORDER)}
    blocks.sort(key=lambda b: rank.get(_title(b), len(rank)))  # stable
    if stale:
        blocks = [
            _mark_stale(b, *stale).rstrip() + "\n" if _title(b) == "Gate verdict" else b
            for b in blocks
        ]
    parts = ["# Calibration report\n", intro.rstrip() + "\n"]
    return "\n".join(parts + blocks)


def write_model_params(elo: dict, alpha: float, chosen_on: str, path=None) -> dict:
    """Write model_params.json, preserving an existing rating_sigma (only
    tournament-check sets it)."""
    path = path or PARAMS_PATH
    sigma = None
    if path.exists():
        try:
            sigma = json.loads(path.read_text()).get("elo-dc-v2", {}).get("rating_sigma")
        except (ValueError, AttributeError):
            sigma = None
    params = {
        "elo-dc-v2": {"elo": elo, "alpha": alpha, "rating_sigma": sigma},
        "chosen_on": chosen_on,
        "tuning_seasons": TUNING_SEASONS,
    }
    path.write_text(json.dumps(params, indent=2) + "\n")
    return params


def _scored(matches, elo, alpha, base):
    preds = walk_forward(matches, elo, REPORT_SEASONS, alpha)
    sc = score(preds)
    d = bootstrap_delta_rps(base, preds) if base is not None else (0.0, 0.0, 0.0)
    return preds, sc, d


def run_backtest(matches: pd.DataFrame | None = None) -> dict:
    """Grid on tuning seasons, select, compare v1 vs chosen v2 on report seasons,
    run diagnostic sensitivity variants, write model_params.json,
    reports/backtest_grid.csv and reports/calibration.md."""
    if matches is None:
        from uclpred.matches import load_matches

        matches = load_matches()
    grid_df = run_grid(matches, TUNING_SEASONS, GRID)
    grid_df = grid_df.sort_values(["rps", "k", "k_euro", "g", "alpha"], kind="stable")
    grid_df = grid_df.reset_index(drop=True)
    ch = select_params(grid_df)
    alt = select_params(grid_df, gap_col="league_gap_tuning")
    elo_keys = ("k", "k_euro", "g")
    same_elo = all(alt[k] == ch[k] for k in elo_keys)
    alt_gap = float(
        grid_df[(grid_df[list(elo_keys)] == pd.Series({k: ch[k] for k in elo_keys})).all(axis=1)][
            "league_gap_tuning"
        ].iloc[0]
    )
    print("chosen:", {k: ch[k] for k in (*elo_keys, "home_adv", "alpha")}, flush=True)

    def v2elo(k, k_euro, g):
        return run_elo_v2(matches, EloV2Params(k=k, k_euro=k_euro, g=g, home_adv=HOME_ADV))

    def gate_gap(elo, home_adv=HOME_ADV, frm=GATE_FROM):
        return league_gap(matches, elo.pre, home_adv, from_season=frm, to_season=GATE_TO)

    elo1 = run_elo(matches)
    elo2 = v2elo(ch["k"], ch["k_euro"], ch["g"])
    p1, s1, _ = _scored(matches, elo1, V1_ALPHA, None)
    p2, s2, (d_mean, d_lo, d_hi) = _scored(matches, elo2, ch["alpha"], p1)
    gap1, n1 = gate_gap(elo1)
    gap2, n2 = gate_gap(elo2)
    gap1r, n1r = gate_gap(elo1, frm=REPORT_SEASONS[0])
    gap2r, n2r = gate_gap(elo2, frm=REPORT_SEASONS[0])

    sens = []
    _, sc, d = _scored(matches, elo1, 0.0005, p1)
    sens.append(("v1 @ alpha 0.0005", sc, d, gate_gap(elo1)[0]))
    _, sc, d = _scored(matches, elo2, V1_ALPHA, p1)
    sens.append(("v2 chosen Elo @ alpha 0.005", sc, d, gap2))
    elo_c = v2elo(**CORNER)
    _, sc, d = _scored(matches, elo_c, V1_ALPHA, p1)
    sens.append(("v2 corner k=32 k_euro=3.0 g=1.0 @ alpha 0.005", sc, d, gate_gap(elo_c)[0]))
    sens_df = pd.DataFrame([
        {
            "variant": name, "rps": sc["rps"], "log_loss": sc["log_loss"], "brier": sc["brier"],
            "delta_rps_vs_v1": d[0], "ci_lo": d[1], "ci_hi": d[2], "gate_gap": gp,
        }
        for name, sc, d, gp in sens
    ])  # fmt: skip

    params = write_model_params(
        {k: ch[k] for k in (*elo_keys, "home_adv")},
        ch["alpha"],
        datetime.now(UTC).date().isoformat(),
    )
    GRID_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    grid_df.to_csv(GRID_CSV_PATH, index=False)

    cal = calibration_table(p2["p_home"].to_numpy(), (p2["outcome"] == 0).to_numpy(), bins=10)
    cmp_df = pd.DataFrame([
        {"model": "elo-dc-v1 (alpha 0.005)", **s1},
        {"model": "elo-dc-v2 (chosen)", **s2},
    ])  # fmt: skip
    scope = f"{GATE_FROM} ... {GATE_TO}"
    gap_df = pd.DataFrame([
        {"model": "elo-dc-v1", "scope": f"Gate 1 scope: {scope}", "gap": gap1, "n": n1},
        {"model": "elo-dc-v2", "scope": f"Gate 1 scope: {scope}", "gap": gap2, "n": n2},
        {"model": "elo-dc-v1", "scope": f"Report seasons only: {REPORT_SEASONS[0]} ... {GATE_TO}",
         "gap": gap1r, "n": n1r},
        {"model": "elo-dc-v2", "scope": f"Report seasons only: {REPORT_SEASONS[0]} ... {GATE_TO}",
         "gap": gap2r, "n": n2r},
    ])  # fmt: skip
    f4 = "{:.4f}"
    metr = {"rps": f4, "log_loss": f4, "brier": f4, "league_gap": "{:.3f}"}
    chosen_df = pd.DataFrame([{**{k: ch[k] for k in (*elo_keys, "home_adv", "alpha")},
                               **{k: ch[k] for k in ("rps", "log_loss", "brier", "league_gap")}}])  # fmt: skip
    cand = tie_candidates(grid_df).drop(columns="league_gap_tuning")
    sections = [
        ("Grid (top 10)", (
            f"Tuning-season mean RPS, {len(grid_df)} grid points, sorted by RPS. "
            "Full grid: `reports/backtest_grid.csv`.\n\n"
            + _md_table(grid_df.head(10).drop(columns="league_gap_tuning"), metr)
        )),
        ("Chosen parameters", (
            _md_table(chosen_df, metr)
            + "\n\nSelection: lowest tuning-season RPS; ties within 0.0005 go to the smaller "
            f"|league gap|. The gap is the Global-Constraints scope ({scope}). A "
            f"tuning-seasons-only gap ({min(TUNING_SEASONS)} ... {max(TUNING_SEASONS)}) "
            f"{'selects the same Elo set' if same_elo else 'would select a DIFFERENT Elo set'} "
            f"(chosen set's tuning-only gap {alt_gap:.3f}).\n\n"
            f"### Candidates within 0.0005 of best ({len(cand)})\n\n" + _md_table(cand, metr)
        )),
        ("Report seasons: v1 vs v2", (
            _md_table(cmp_df, {"rps": f4, "log_loss": f4, "brier": f4})
            + f"\n\nDelta RPS (v2 - v1): {d_mean:+.4f}, 95% CI [{d_lo:+.4f}, {d_hi:+.4f}] "
            "(1,000 bootstrap resamples of match ids, seed 1)."
        )),
        ("Sensitivity (outside the pre-registered selection)", (
            "Diagnostic evaluations on the report seasons for the gate decision, not a "
            "re-selection. All rows use identical matches; delta is vs v1 @ alpha 0.005 "
            f"(95% bootstrap CI); gate_gap uses the Gate 1 scope ({scope}).\n\n"
            + _md_table(sens_df, {c: f4 for c in sens_df.columns if c not in ("variant", "gate_gap")}
                        | {"gate_gap": "{:.3f}"})
        )),
        ("Calibration (v2)", (
            "Home-win probability bins on report seasons.\n\n"
            + _md_table(cal, {"bin_lo": "{:.1f}", "bin_hi": "{:.1f}", "mean_pred": f4,
                              "observed": f4})
        )),
        ("League gap", (
            "Mean (actual - expected Elo score) for mid-league clubs against Big-5 clubs "
            "in European matches, capped at season "
            f"{GATE_TO}.\n\n" + _md_table(gap_df, {"gap": "{:.3f}"})
        )),
    ]  # fmt: skip
    intro = (
        f"Elo v2 parameter search and v1 vs v2 backtest, generated {params['chosen_on']} by "
        "`uv run uclpred backtest`. Parameters chosen on tuning seasons "
        f"{', '.join(TUNING_SEASONS)}; compared on report seasons {', '.join(REPORT_SEASONS)}."
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = REPORT_PATH.read_text() if REPORT_PATH.exists() else None
    REPORT_PATH.write_text(merge_report(existing, intro, sections, stale=("`uclpred backtest`", params["chosen_on"])))
    print(f"v1: {s1}\nv2: {s2}", flush=True)
    print(f"delta rps v2-v1: {d_mean:+.4f} CI [{d_lo:+.4f}, {d_hi:+.4f}]", flush=True)
    print(f"gap v1 {gap1:.3f} (n={n1}), v2 {gap2:.3f} (n={n2})", flush=True)
    print(sens_df.to_string(), flush=True)
    return {"chosen": ch, "v1": s1, "v2": s2, "delta": (d_mean, d_lo, d_hi), "gaps": (gap1, gap2)}
