"""Walk-forward backtest engine and paired bootstrap of the RPS difference."""

import itertools
import json
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
TUNING_SEASONS = ["2019-20", "2020-21", "2021-22"]
REPORT_SEASONS = ["2022-23", "2023-24", "2024-25", "2025-26"]
HOME_ADV = 60.0
V1_ALPHA = 0.005
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
    """One row per (k, k_euro, g, alpha). Elo v2 and the league gap are computed
    once per Elo-parameter set and shared across its alpha rows."""
    rows = []
    elo_sets = list(itertools.product(grid["k"], grid["k_euro"], grid["g"]))
    for i, (k, k_euro, g) in enumerate(elo_sets, 1):
        print(f"[grid {i}/{len(elo_sets)}] k={k} k_euro={k_euro} g={g}", flush=True)
        elo = run_elo_v2(matches, EloV2Params(k=k, k_euro=k_euro, g=g, home_adv=HOME_ADV))
        gap, _ = league_gap(matches, elo.pre, HOME_ADV)
        for alpha in grid["alpha"]:
            sc = score(walk_forward(matches, elo, tuning_seasons, alpha))
            rows.append({
                "k": k, "k_euro": k_euro, "g": g, "alpha": alpha,
                "rps": sc["rps"], "log_loss": sc["log_loss"], "brier": sc["brier"],
                "league_gap": gap,
            })  # fmt: skip
    return pd.DataFrame(rows)


def select_params(grid_df: pd.DataFrame) -> dict:
    """Lowest RPS wins; rows within TIE_TOL of the best go to the smaller
    |league_gap|; remaining ties break on k, k_euro, g, alpha."""
    best = grid_df["rps"].min()
    cand = grid_df[grid_df["rps"] <= best + TIE_TOL].copy()
    cand["_abs_gap"] = cand["league_gap"].abs()
    cand = cand.sort_values(
        ["_abs_gap", "rps", "k", "k_euro", "g", "alpha"], kind="stable"
    )
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
        out.append(
            "| " + " | ".join(fmt.get(c, "{}").format(v) for c, v in zip(cols, r)) + " |"
        )
    return "\n".join(out)


def run_backtest(matches: pd.DataFrame | None = None) -> dict:
    """Grid on tuning seasons, select, compare v1 vs chosen v2 on report seasons,
    write model_params.json and reports/calibration.md."""
    if matches is None:
        from uclpred.matches import load_matches

        matches = load_matches()
    grid_df = run_grid(matches, TUNING_SEASONS, GRID)
    grid_df = grid_df.sort_values(
        ["rps", "k", "k_euro", "g", "alpha"], kind="stable"
    ).reset_index(drop=True)
    ch = select_params(grid_df)
    print("chosen:", {k: ch[k] for k in ("k", "k_euro", "g", "home_adv", "alpha")}, flush=True)

    elo1 = run_elo(matches)
    elo2 = run_elo_v2(
        matches,
        EloV2Params(k=ch["k"], k_euro=ch["k_euro"], g=ch["g"], home_adv=ch["home_adv"]),
    )
    p1 = walk_forward(matches, elo1, REPORT_SEASONS, V1_ALPHA)
    p2 = walk_forward(matches, elo2, REPORT_SEASONS, ch["alpha"])
    s1, s2 = score(p1), score(p2)
    d_mean, d_lo, d_hi = bootstrap_delta_rps(p1, p2)
    gap1, n1 = league_gap(matches, elo1.pre, HOME_ADV)
    gap2, n2 = league_gap(matches, elo2.pre, ch["home_adv"])
    gap1r, n1r = league_gap(matches, elo1.pre, HOME_ADV, from_season=REPORT_SEASONS[0])
    gap2r, n2r = league_gap(matches, elo2.pre, ch["home_adv"], from_season=REPORT_SEASONS[0])

    params = {
        "elo-dc-v2": {
            "elo": {k: ch[k] for k in ("k", "k_euro", "g", "home_adv")},
            "alpha": ch["alpha"],
            "rating_sigma": None,
        },
        "chosen_on": datetime.now(UTC).date().isoformat(),
        "tuning_seasons": TUNING_SEASONS,
    }
    PARAMS_PATH.write_text(json.dumps(params, indent=2) + "\n")

    top = grid_df.head(10)
    cal = calibration_table(p2["p_home"].to_numpy(), (p2["outcome"] == 0).to_numpy(), bins=10)
    cmp_df = pd.DataFrame([
        {"model": "elo-dc-v1 (alpha 0.005)", **s1},
        {"model": "elo-dc-v2 (chosen)", **s2},
    ])  # fmt: skip
    gap_df = pd.DataFrame([
        {"model": "elo-dc-v1", "scope": "2019-20 onwards", "gap": gap1, "n": n1},
        {"model": "elo-dc-v2", "scope": "2019-20 onwards", "gap": gap2, "n": n2},
        {"model": "elo-dc-v1", "scope": "report seasons", "gap": gap1r, "n": n1r},
        {"model": "elo-dc-v2", "scope": "report seasons", "gap": gap2r, "n": n2r},
    ])  # fmt: skip
    f4 = "{:.4f}"
    md = [
        "# Calibration report",
        "",
        (
            f"Elo v2 parameter search and v1 vs v2 backtest, generated {params['chosen_on']} by "
            "`uv run uclpred backtest`. Parameters chosen on tuning seasons "
            f"{', '.join(TUNING_SEASONS)}; compared on report seasons "
            f"{', '.join(REPORT_SEASONS)}."
        ),
        "",
        "## Grid (top 10)",
        "",
        f"Tuning-season mean RPS, {len(grid_df)} grid points, sorted by RPS.",
        "",
        _md_table(top, {"rps": f4, "log_loss": f4, "brier": f4, "league_gap": "{:.3f}"}),
        "",
        "## Chosen parameters",
        "",
        _md_table(
            pd.DataFrame([{k: ch[k] for k in ("k", "k_euro", "g", "home_adv", "alpha")}])
        ),
        "",
        "Selection: lowest tuning-season RPS; ties within 0.0005 go to the smaller |league gap|.",
        "",
        "## Report seasons: v1 vs v2",
        "",
        _md_table(cmp_df, {"rps": f4, "log_loss": f4, "brier": f4}),
        "",
        (
            f"Delta RPS (v2 - v1): {d_mean:+.4f}, 95% CI [{d_lo:+.4f}, {d_hi:+.4f}] "
            "(1,000 bootstrap resamples of match ids, seed 1)."
        ),
        "",
        "## Calibration (v2)",
        "",
        "Home-win probability bins on report seasons.",
        "",
        _md_table(cal, {"bin_lo": "{:.1f}", "bin_hi": "{:.1f}", "mean_pred": f4, "observed": f4}),
        "",
        "## League gap",
        "",
        (
            "Mean (actual - expected Elo score) for mid-league clubs against Big-5 clubs "
            "in European matches."
        ),
        "",
        _md_table(gap_df, {"gap": "{:.3f}"}),
        "",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(md))
    print(f"v1: {s1}\nv2: {s2}", flush=True)
    print(f"delta rps v2-v1: {d_mean:+.4f} CI [{d_lo:+.4f}, {d_hi:+.4f}]", flush=True)
    print(f"gap v1 {gap1:.3f} (n={n1}), v2 {gap2:.3f} (n={n2})", flush=True)
    return {"chosen": ch, "v1": s1, "v2": s2, "delta": (d_mean, d_lo, d_hi), "gaps": (gap1, gap2)}
