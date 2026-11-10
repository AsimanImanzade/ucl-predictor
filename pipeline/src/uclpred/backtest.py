"""Walk-forward backtest engine and paired bootstrap of the RPS difference."""

import itertools

import numpy as np
import pandas as pd

from uclpred.elo import EloResult
from uclpred.models.baseline import fit_baseline
from uclpred.models.metrics import brier, log_loss, rps
from uclpred.models.score_matrix import outcome_probs

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
