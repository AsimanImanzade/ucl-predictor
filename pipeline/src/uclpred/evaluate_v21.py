"""Pre-registered v2.1 evaluation: gates G1-G3, diagnostics, report.

Data layer: `compute_v21` / `run_evaluate_v21`. Pure functions: `gate_results`,
`render_report`, run-log helpers."""

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

THRESHOLDS = {"G1": 0.03, "G2": 0.003, "G3": 0.006}
HOLDOUT = (pd.Timestamp("2026-09-07", tz="UTC"), pd.Timestamp("2026-11-09", tz="UTC"))
REPORT_SEASONS = ["2022-23", "2023-24", "2024-25", "2025-26"]
TOURNAMENT_SEASONS = ["2024-25", "2025-26"]
TOURNAMENT_MODELS = ["elo-dc-v1", "elo-dc-v2.1"]
PREREG_COMMIT = "381a8a8"
V1_ALPHA = 0.005
HOME_ADV = 60
REPORT_NAME = "v21-evaluation.md"
SECTIONS = ["Verdict", "Settings", "Gates", "Diagnostics", "Run log"]
RUN_RE = re.compile(r"\brun (\d+)\b")
JSON_NAME = "v21-evaluation.json"
PREREG_SETTINGS = {
    "elo": {"k": 24, "k_euro": 2.0, "g": 0.9, "g_pseudo": 0.0, "home_adv": 60},
    "alpha": 0.005,
    "rating_sigma": 0,
}
CAL_LABEL = "uefa.* 2022-26"
HOLD_LABEL = "holdout (all competitions)"


def gate_results(g1_gap: float, g2_ci_hi: float, g3_ci_hi: float) -> dict[str, bool]:
    return {
        "G1": abs(g1_gap) <= THRESHOLDS["G1"],
        "G2": g2_ci_hi <= THRESHOLDS["G2"],
        "G3": g3_ci_hi <= THRESHOLDS["G3"],
    }


def _gates_of(results: dict) -> dict[str, bool]:
    return gate_results(results["g1"]["v21"], results["g2"]["hi"], results["g3"]["hi"])


# ---------------------------------------------------------------- run log
def _sections(text: str) -> list[tuple[str, str]]:
    """Split on level-2 headings: [(heading, raw block incl. heading line)]."""
    parts = re.split(r"(?m)^(?=## )", text)
    out = []
    for blk in parts:
        m = re.match(r"## (.*?)\s*$", blk.split("\n", 1)[0])
        if m:
            out.append((m.group(1), blk))
    return out


def existing_run_lines(path: Path) -> list[str]:
    """Verbatim non-empty lines of the Run log body (up to the next `## `)."""
    if not path.exists():
        return []
    for heading, blk in _sections(path.read_text(encoding="utf-8")):
        if heading == "Run log":
            return [ln for ln in blk.splitlines()[1:] if ln.strip()]
    return []


def preserved_sections(path: Path) -> list[str]:
    """Raw blocks of sections this module does not own (e.g. G4 review/context)."""
    if not path.exists():
        return []
    return [
        blk.rstrip("\n")
        for heading, blk in _sections(path.read_text(encoding="utf-8"))
        if heading not in SECTIONS
    ]


def append_run_line(path: Path, line: str) -> None:
    """Append a line at the end of the Run log section, wherever it sits."""
    text = path.read_text(encoding="utf-8")
    secs = _sections(text)
    pre = text[: len(text) - sum(len(b) for _, b in secs)]
    out = []
    for heading, blk in secs:
        if heading == "Run log":
            blk = blk.rstrip("\n") + "\n" + line + "\n"
            if heading != secs[-1][0]:
                blk += "\n"
        out.append(blk)
    path.write_text(pre + "".join(out), encoding="utf-8")


def next_run_number(path: Path) -> int:
    nums = [
        int(m.group(1)) for ln in existing_run_lines(path) if (m := RUN_RE.search(ln))
    ]
    return 1 + max(nums, default=0)


def _ts(now: datetime | None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")


def start_line(
    n: int, sha: str, reason: str | None = None, now: datetime | None = None
) -> str:
    reason = " ".join(reason.split()) if reason else None
    tail = f" (reason: {reason})" if reason else ""
    return f"- {_ts(now)} {sha} run {n} started{tail}"


def _fmt_gate(g: str, results: dict, ok: bool) -> str:
    v = {
        "G1": results["g1"]["v21"],
        "G2": results["g2"]["hi"],
        "G3": results["g3"]["hi"],
    }[g]
    return f"{g} {v:+.9f} {'PASS' if ok else 'FAIL'}"


def verdict_text(results: dict) -> str:
    failing = [g for g, ok in _gates_of(results).items() if not ok]
    if not failing:
        return "G1–G3: PASS — pending user review (G4)"
    return f"FAIL ({', '.join(failing)}) — v1 stays default"


def result_line(n: int, results: dict, now: datetime | None = None) -> str:
    gates = _gates_of(results)
    vals = "; ".join(_fmt_gate(g, results, ok) for g, ok in gates.items())
    return f"- {_ts(now)} run {n} result: {vals}; G4 pending user review; verdict: {verdict_text(results)}"


def failure_line(n: int, err: str, now: datetime | None = None) -> str:
    return f"- {_ts(now)} run {n} FAILED: {' '.join(err.split())[:300]}"


# ----------------------------------------------------------------- render
def _md_table(header: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
    ]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def _tournament_md(results: dict, tour_rows: list[list[str]]) -> str:
    if results.get("tournament_error"):
        return f"ERROR (not gating): {results['tournament_error']}"
    if results.get("tournament") is None:
        return "pending"
    return _md_table(["Season", "Model", "stage_log_loss"], tour_rows)


def render_report(
    results: dict, run_lines: list[str], extra: list[str] | None = None
) -> str:
    gates = _gates_of(results)
    verdict = verdict_text(results)
    s = results["settings"]
    e = s["elo"]
    settings = (
        f"Pre-registered in commit `{PREREG_COMMIT}` (§2); read from `model_params.json`, "
        "not tuned.\n\n"
        + _md_table(
            ["Setting", "Value"],
            [
                ["Model", "`elo-dc-v2.1` vs `elo-dc-v1` (`run_elo`, alpha 0.005)"],
                [
                    "Elo",
                    f"`run_elo_v2` k={e['k']}, k_euro={e['k_euro']}, g={e['g']}, "
                    + (f"g_pseudo={e.get('g_pseudo')}, home_adv={e['home_adv']}"),
                ],
                [
                    "GLM",
                    f"`fit_baseline` alpha={s['alpha']}; xi=0.0019, window_days=1460, "
                    + "euro_weight=2.0",
                ],
                ["Rating uncertainty", f"sigma = {s['rating_sigma']}"],
                ["Bootstrap", "1,000 match resamples, seed 1, 95% percentile CI"],
            ],
        )
    )
    g1, g2, g3 = results["g1"], results["g2"], results["g3"]
    ok = {g: "PASS" if v else "FAIL" for g, v in gates.items()}
    gate_rows = [
        [
            "G1",
            f"{g1['v21']:+.9f} (n={g1['n']}; v1 {g1['v1']:+.9f})",
            "\\|gap(v2.1)\\| ≤ 0.03",
            ok["G1"],
        ],
        ["G2", f"{g2['hi']:+.9f} (ΔRPS CI upper)", "≤ +0.003", ok["G2"]],
        ["G3", f"{g3['hi']:+.9f} (ΔRPS CI upper)", "≤ +0.006", ok["G3"]],
        ["G4", "user review", "user says yes", "pending user review"],
    ]
    gates_md = _md_table(["Gate", "Value", "Threshold", "Result"], gate_rows)

    def delta_line(name, g, window):
        return (
            f"- {name} ({window}, n={g['n']}): RPS v1 {g['rps_v1']:.4f}, v2.1 "
            f"{g['rps_v21']:.4f}; ΔRPS {g['mean']:+.9f} "
            f"[{g['lo']:+.9f}, {g['hi']:+.9f}]"
        )

    cal_rows = []
    for win, d in results["calib"].items():
        for model, (mp, obs) in d.items():
            cal_rows.append([win, model, f"{mp:.4f}", f"{obs:.4f}", f"{mp - obs:+.4f}"])
    comp_rows = [
        [c["competition"], str(c["n"]), f"{c['rps_v1']:.4f}", f"{c['rps_v21']:.4f}"]
        for c in results["g3_by_comp"]
    ]
    tour = results.get("tournament") or []
    tour_rows = [[t["season"], t["model"], f"{t['stage_log_loss']:.4f}"] for t in tour]
    for m in TOURNAMENT_MODELS:
        v = [t["stage_log_loss"] for t in tour if t["model"] == m]
        if v:
            tour_rows.append(["mean", m, f"{sum(v) / len(v):.4f}"])
    diag = "\n\n".join(
        [
            "### Deltas\n\n"
            + delta_line("G2", g2, "uefa.*, 2022-23 … 2025-26")
            + "\n"
            + delta_line("G3", g3, "all competitions, holdout"),
            "### Home-win calibration\n\n"
            + _md_table(
                ["Window", "Model", "Mean p_home", "Observed", "Diff"], cal_rows
            ),
            "### G3 by competition\n\n"
            + _md_table(["Competition", "n", "RPS v1", "RPS v2.1"], comp_rows),
            "### Tournament check (reported, not gating; sigma 0, 50,000 runs, seed 1)\n\n"
            + _tournament_md(results, tour_rows),
        ]
    )
    body = {
        "Verdict": verdict,
        "Settings": settings,
        "Gates": gates_md,
        "Diagnostics": diag,
        "Run log": "\n".join(run_lines),
    }
    blocks = [f"## {h}\n\n{body[h]}".rstrip() for h in SECTIONS]
    blocks[-1:-1] = [x.rstrip("\n") for x in extra or []]  # above the Run log
    return "# v2.1 evaluation\n\n" + "\n\n".join(blocks) + "\n"


# --------------------------------------------------------------- data layer
def _calib(preds: pd.DataFrame) -> tuple[float, float]:
    return float(preds["p_home"].mean()), float((preds["outcome"] == 0).mean())


def _delta(p1: pd.DataFrame, p21: pd.DataFrame) -> dict:
    from uclpred.backtest import bootstrap_delta_rps, score

    mean, lo, hi = bootstrap_delta_rps(p1, p21)
    return {
        "mean": mean, "lo": lo, "hi": hi, "n": len(p1),
        "rps_v1": score(p1)["rps"], "rps_v21": score(p21)["rps"],
    }  # fmt: skip


def _by_competition(
    matches: pd.DataFrame, p1: pd.DataFrame, p21: pd.DataFrame
) -> list[dict]:
    from uclpred.backtest import _arrays, _per_match_rps

    comp = matches.drop_duplicates("match_id").set_index("match_id")["competition"]
    a = p1.set_index("match_id").sort_index()
    b = p21.set_index("match_id").sort_index()
    r1 = pd.Series(_per_match_rps(*_arrays(a)), index=a.index)
    r2 = pd.Series(_per_match_rps(*_arrays(b)), index=b.index)
    df = pd.DataFrame({"competition": comp.reindex(a.index), "r1": r1, "r2": r2})
    g = df.groupby("competition").agg(
        n=("r1", "size"), rps_v1=("r1", "mean"), rps_v21=("r2", "mean")
    )
    return [
        {
            "competition": c,
            "n": int(r.n),
            "rps_v1": float(r.rps_v1),
            "rps_v21": float(r.rps_v21),
        }
        for c, r in g.sort_values("n", ascending=False).iterrows()
    ]


def tournament_rows(runs: int = 50000) -> list[dict]:
    """Per season/model stage_log_loss at sigma 0 from fresh preseason exports."""
    from uclpred.config import EXPORT, PROCESSED, SEASONS
    from uclpred.export import run_export
    from uclpred.teams import TeamResolver
    from uclpred.tournament_check import (
        _run_sim,
        actual_outcomes,
        actual_top8,
        score_tournament,
    )  # fmt: skip

    resolver = TeamResolver()
    rows = []
    for season in TOURNAMENT_SEASONS:
        y = SEASONS[season]["fd_year"]
        fd = json.loads((PROCESSED / f"cl_{y}_fd.json").read_text(encoding="utf-8"))
        teams = json.loads((PROCESSED / f"cl_{y}_teams.json").read_text(encoding="utf-8"))
        tc = {t["id"]: t["area"]["code"] for t in teams}
        actual, top8 = actual_outcomes(fd, resolver, tc), actual_top8(fd, resolver, tc)
        for model in TOURNAMENT_MODELS:
            run_export(
                as_of=SEASONS[season]["preseason_as_of"],
                out=EXPORT / "bt" / season / model,
                season=season,
                model_name=model,
            )
            _run_sim(season, model, 0, runs)
            path = EXPORT / "bt" / season / model / "chances_s0.json"
            chances = json.loads(path.read_text(encoding="utf-8"))["chances"]
            rows.append({"season": season, "model": model,
                         **score_tournament(chances, actual, top8)})  # fmt: skip
    return rows


def check_settings(params: dict) -> None:
    """Abort unless model_params.json's elo-dc-v2.1 entry equals pre-registration §2."""
    entry = params.get("elo-dc-v2.1")
    if entry != PREREG_SETTINGS:
        raise ValueError(
            f"model_params.json 'elo-dc-v2.1' differs from the pre-registration: "
            f"{entry!r} != {PREREG_SETTINGS!r}"
        )


def holdout_count(matches: pd.DataFrame) -> int:
    d = matches["date"]
    return int(
        ((matches["status"] == "FINISHED") & (d >= HOLDOUT[0]) & (d < HOLDOUT[1])).sum()
    )


def preflight(matches: pd.DataFrame, params: dict) -> None:
    """Raise on anything that would make the single run fail late."""
    import shutil

    from uclpred.config import PROCESSED, REFERENCE

    needed = [PROCESSED / "matches.parquet", REFERENCE / "coefficients.csv"]
    for y in (2024, 2025):
        needed += [PROCESSED / f"cl_{y}_fd.json", PROCESSED / f"cl_{y}_teams.json"]
    missing = [str(p) for p in needed if not p.exists()]
    if missing:
        raise FileNotFoundError(f"pre-flight: missing input files: {missing}")
    if not shutil.which("pnpm"):
        raise RuntimeError("pre-flight: pnpm not found on PATH")
    if holdout_count(matches) == 0:
        raise RuntimeError("pre-flight: holdout selection is empty")
    check_settings(params)


def compute_core(matches: pd.DataFrame, params: dict) -> dict:
    """G1-G3 and the cheap diagnostics (pre-registered computation)."""
    from uclpred.backtest import walk_forward
    from uclpred.elo import run_elo
    from uclpred.elo_v2 import EloV2Params, run_elo_v2
    from uclpred.models.metrics import league_gap

    entry = params["elo-dc-v2.1"]
    elo1 = run_elo(matches)
    elo21 = run_elo_v2(matches, EloV2Params(**entry["elo"]))
    a1, a21 = V1_ALPHA, entry["alpha"]

    def gap(elo):
        return league_gap(
            matches, elo.pre, HOME_ADV, from_season="2022-23", to_season="2025-26"
        )

    gap21, n_gap = gap(elo21)
    gap1, _ = gap(elo1)

    q1 = walk_forward(matches, elo1, REPORT_SEASONS, a1)
    q21 = walk_forward(matches, elo21, REPORT_SEASONS, a21)
    h1 = walk_forward(matches, elo1, None, a1, prefixes=None, window=HOLDOUT)
    h21 = walk_forward(matches, elo21, None, a21, prefixes=None, window=HOLDOUT)
    return {
        "settings": {
            "elo": entry["elo"],
            "alpha": a21,
            "rating_sigma": entry["rating_sigma"],
        },
        "g1": {"v21": gap21, "v1": gap1, "n": n_gap},
        "g2": _delta(q1, q21),
        "g3": _delta(h1, h21),
        "calib": {
            CAL_LABEL: {"v1": _calib(q1), "v2.1": _calib(q21)},
            HOLD_LABEL: {"v1": _calib(h1), "v2.1": _calib(h21)},
        },
        "g3_by_comp": _by_competition(matches, h1, h21),
        "tournament": None,
    }


def add_tournament(results: dict, runs: int = 50000) -> dict:
    """Reported, not gating: a failure is recorded, never raised."""
    try:
        results["tournament"] = tournament_rows(runs)
    except Exception as e:  # noqa: BLE001
        results["tournament"] = None
        results["tournament_error"] = f"{type(e).__name__}: {e}"
    return results


def compute_v21(matches: pd.DataFrame, params: dict, runs: int = 50000) -> dict:
    return add_tournament(compute_core(matches, params), runs)


def _git_describe() -> str:
    from uclpred.config import ROOT

    return subprocess.run(
        ["git", "describe", "--always", "--dirty", "--abbrev=7"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()  # fmt: skip


def _write(
    results: dict,
    lines: list[str],
    md_path: Path,
    json_path: Path,
    n: int,
    sha: str,
) -> None:
    extra = preserved_sections(md_path)
    md_path.write_text(render_report(results, lines, extra), encoding="utf-8")
    payload = {"run": n, "head": sha, **results}
    json_path.write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )


def run_evaluate_v21(runs: int = 50000, reason: str | None = None) -> dict:
    from uclpred.backtest import load_model_params
    from uclpred.config import REPORTS
    from uclpred.matches import load_matches

    path, jpath = REPORTS / REPORT_NAME, REPORTS / JSON_NAME
    prev = existing_run_lines(path)
    if prev and not reason:
        raise ValueError(
            "a previous run exists: --reason TEXT is required to record why"
        )
    n, sha = next_run_number(path), _git_describe()
    params = load_model_params()
    matches = load_matches()
    preflight(matches, params)
    REPORTS.mkdir(parents=True, exist_ok=True)
    lines = [*prev, start_line(n, sha, reason)]
    if prev:
        append_run_line(path, lines[-1])
    else:
        path.write_text(
            f"# v2.1 evaluation\n\n## Run log\n\n{lines[-1]}\n", encoding="utf-8"
        )
    try:
        results = compute_core(matches, params)
        lines.append(result_line(n, results))
        _write(results, lines, path, jpath, n, sha)
        add_tournament(results, runs)
        _write(results, lines, path, jpath, n, sha)
    except Exception as e:
        append_run_line(path, failure_line(n, f"{type(e).__name__}: {e}"))
        raise
    gates = _gates_of(results)
    print({g: ("PASS" if v else "FAIL") for g, v in gates.items()}, f"-> {path}")
    return {**results, "gates": gates}
