import numpy as np
import pandas as pd

from uclpred.elo import expected_home

MID_LEAGUES = frozenset({"nl.1", "pt.1", "tr.1", "gr.1", "be.1", "sco.1", "at.1"})
BIG5_LEAGUES = frozenset({"en.1", "es.1", "de.1", "it.1", "fr.1"})


def rps(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Mean ranked probability score for 3 ordered outcomes (0 home, 1 draw, 2 away).

    Per match: 1/2 * sum_{k=1..2} (cumulative predicted_k - cumulative observed_k)^2.
    """
    probs = np.asarray(probs, dtype=float)
    obs = np.zeros_like(probs)
    obs[np.arange(len(probs)), np.asarray(outcomes, dtype=int)] = 1.0
    diff = np.cumsum(probs, axis=1) - np.cumsum(obs, axis=1)
    return float(np.mean(0.5 * (diff[:, :2] ** 2).sum(axis=1)))


def log_loss(probs: np.ndarray, outcomes: np.ndarray, eps: float = 1e-12) -> float:
    """Mean -log p of the observed outcome, probabilities clipped to [eps, 1]."""
    probs = np.asarray(probs, dtype=float)
    p = np.clip(probs[np.arange(len(probs)), np.asarray(outcomes, dtype=int)], eps, 1.0)
    return float(np.mean(-np.log(p)))


def brier(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Mean over matches of sum_k (p_k - 1[k == outcome])^2."""
    probs = np.asarray(probs, dtype=float)
    obs = np.zeros_like(probs)
    obs[np.arange(len(probs)), np.asarray(outcomes, dtype=int)] = 1.0
    return float(np.mean(((probs - obs) ** 2).sum(axis=1)))


def calibration_table(p_home: np.ndarray, home_won: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """Equal-width bins on [0, 1]; last bin closed at 1.0; empty bins kept with NaNs."""
    p = np.asarray(p_home, dtype=float)
    y = np.asarray(home_won, dtype=float)
    idx = np.minimum((p * bins).astype(int), bins - 1)
    rows = []
    for i in range(bins):
        mask = idx == i
        n = int(mask.sum())
        rows.append({
            "bin_lo": i / bins,
            "bin_hi": (i + 1) / bins,
            "n": n,
            "mean_pred": float(p[mask].mean()) if n else float("nan"),
            "observed": float(y[mask].mean()) if n else float("nan"),
        })  # fmt: skip
    return pd.DataFrame(rows)


def league_gap(
    matches: pd.DataFrame,
    elo_pre: pd.DataFrame,
    home_adv: float,
    from_season: str = "2019-20",
    to_season: str | None = None,
) -> tuple[float, int]:
    """Mean (actual - expected Elo score) from the mid-league side of European
    matches between a mid-league club and a Big-5 club.

    A club's label in a season is the competition of its last domestic FINISHED
    match that season. European matches are limited to seasons in
    [from_season, to_season]; to_season=None means no upper cap.
    """
    fin = matches[matches["status"] == "FINISHED"]
    dom = fin[~fin["competition"].str.startswith("uefa.")].sort_values(
        ["date", "match_id"], kind="stable"
    )
    sides = pd.concat([
        dom[["season", "date", "match_id", "home_id", "competition"]].rename(
            columns={"home_id": "club"}),
        dom[["season", "date", "match_id", "away_id", "competition"]].rename(
            columns={"away_id": "club"}),
    ]).sort_values(["date", "match_id"], kind="stable")  # fmt: skip
    label = sides.groupby(["season", "club"])["competition"].last().to_dict()

    eu = fin[fin["competition"].str.startswith("uefa.") & (fin["season"] >= from_season)]
    if to_season is not None:
        eu = eu[eu["season"] <= to_season]
    pre = elo_pre.set_index("match_id")
    missing = [m for m in eu["match_id"] if m not in pre.index]
    if missing:
        raise ValueError(f"{len(missing)} European matches missing from elo_pre, e.g. {missing[:3]}")

    resid = []
    for r in eu.itertuples(index=False):
        lh = label.get((r.season, r.home_id))
        la = label.get((r.season, r.away_id))
        if lh in MID_LEAGUES and la in BIG5_LEAGUES:
            home_mid = True
        elif la in MID_LEAGUES and lh in BIG5_LEAGUES:
            home_mid = False
        else:
            continue
        hg, ag = int(r.home_goals), int(r.away_goals)
        s = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
        row = pre.loc[r.match_id]
        e = expected_home(
            float(row["home_elo_pre"]), float(row["away_elo_pre"]),
            0.0 if r.neutral else home_adv,
        )  # fmt: skip
        resid.append(s - e if home_mid else e - s)
    if not resid:
        return float("nan"), 0
    return float(np.mean(resid)), len(resid)
