"""Baseline goal model: weighted Poisson GLM on Elo difference + team attack/defence,
with a Dixon-Coles rho fitted on top.

    log lambda = mu + h*is_home + beta*(elo_team - elo_opp)/100 + attack[team] + defence[opp]

Sign convention: the fitted `defence[opp]` coefficient is added as-is, so a POSITIVE
defence coefficient means that opponent concedes MORE goals (it is a leakiness term).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.optimize import minimize_scalar
from sklearn.linear_model import PoissonRegressor

from uclpred.elo import EloResult
from uclpred.models.score_matrix import score_matrix


@dataclass
class BaselineModel:
    as_of: datetime
    rho: float
    mu: float
    coef_home: float
    coef_elo: float
    attack: dict[str, float]
    defence: dict[str, float]
    # Elo of every team rated as of `as_of` (strictly-before semantics)
    ratings: dict[str, float] = field(repr=False)
    mean_elo: float = 1500.0

    def _elo(self, team: str) -> float:
        # A team with no Elo as of as_of gets the mean rating of rated teams.
        return self.ratings.get(team, self.mean_elo)

    def _lambda(self, team: str, opp: str, is_home: bool) -> float:
        # Teams unseen in the training window: attack = defence = 0.
        eta = (
            self.mu
            + self.coef_home * is_home
            + self.coef_elo * (self._elo(team) - self._elo(opp)) / 100
            + self.attack.get(team, 0.0)
            + self.defence.get(opp, 0.0)
        )
        return float(np.exp(eta))

    def lambdas(
        self, team_a: str, team_b: str, venue: Literal["home", "neutral"]
    ) -> tuple[float, float]:
        """(λ_a, λ_b); team_a hosts when venue == "home"."""
        return (
            self._lambda(team_a, team_b, venue == "home"),
            self._lambda(team_b, team_a, False),
        )

    def predict_match(self, home_id: str, away_id: str, neutral: bool = False) -> np.ndarray:
        lh, la = self.lambdas(home_id, away_id, "neutral" if neutral else "home")
        return score_matrix(lh, la, self.rho)


def _neg_weighted_loglik(rho, hg, ag, lh, la, w):
    t = np.ones_like(lh)
    m00 = (hg == 0) & (ag == 0)
    m01 = (hg == 0) & (ag == 1)
    m10 = (hg == 1) & (ag == 0)
    m11 = (hg == 1) & (ag == 1)
    t[m00] = 1 - lh[m00] * la[m00] * rho
    t[m01] = 1 + lh[m01] * rho
    t[m10] = 1 + la[m10] * rho
    t[m11] = 1 - rho
    return -float(np.sum(w * np.log(np.clip(t, 1e-10, None))))


def fit_baseline(
    matches: pd.DataFrame,
    elo: EloResult,
    as_of: datetime,
    xi: float = 0.0019,
    window_days: int = 1460,
    alpha: float = 0.005,
    euro_weight: float = 2.0,
) -> BaselineModel:
    as_of_ts = pd.Timestamp(as_of)
    lo = as_of_ts - timedelta(days=window_days)
    m = matches[
        (matches["status"] == "FINISHED") & (matches["date"] >= lo) & (matches["date"] < as_of_ts)
    ]
    m = m.merge(elo.pre, on="match_id", how="inner")
    n = len(m)
    if n == 0:
        raise ValueError("no training matches in window")

    teams = sorted(set(m["home_id"]) | set(m["away_id"]))
    idx = {t: i for i, t in enumerate(teams)}
    k = len(teams)
    hi = m["home_id"].map(idx).to_numpy()
    ai = m["away_id"].map(idx).to_numpy()
    hg = m["home_goals"].to_numpy(dtype=float)
    ag = m["away_goals"].to_numpy(dtype=float)
    diff = (m["home_elo_pre"] - m["away_elo_pre"]).to_numpy(dtype=float) / 100
    is_home = (~m["neutral"].astype(bool)).to_numpy(dtype=float)

    # rows 0..n-1: home team's perspective; rows n..2n-1: away team's perspective
    team_idx = np.concatenate([hi, ai])
    opp_idx = np.concatenate([ai, hi])
    rows = np.arange(2 * n)
    X = sp.hstack(
        [
            sp.csr_matrix(np.concatenate([is_home, np.zeros(n)])[:, None]),
            sp.csr_matrix(np.concatenate([diff, -diff])[:, None]),
            sp.csr_matrix((np.ones(2 * n), (rows, team_idx)), shape=(2 * n, k)),
            sp.csr_matrix((np.ones(2 * n), (rows, opp_idx)), shape=(2 * n, k)),
        ],
        format="csr",
    )
    y = np.concatenate([hg, ag])

    days = (as_of_ts - m["date"]).dt.total_seconds().to_numpy() / 86400
    w = np.exp(-xi * days) * np.where(m["competition"].str.startswith("uefa."), euro_weight, 1.0)
    sw = np.concatenate([w, w])

    reg = PoissonRegressor(alpha=alpha, fit_intercept=True, max_iter=1000)
    reg.fit(X, y, sample_weight=sw)
    mu_hat = reg.predict(X)
    lh, la = mu_hat[:n], mu_hat[n:]

    res = minimize_scalar(
        _neg_weighted_loglik,
        bounds=(-0.25, 0.25),
        method="bounded",
        args=(hg, ag, lh, la, w),
    )
    coef = reg.coef_
    ratings = elo.ratings_as_of(as_of)
    return BaselineModel(
        as_of=as_of,
        rho=float(res.x),
        mu=float(reg.intercept_),
        coef_home=float(coef[0]),
        coef_elo=float(coef[1]),
        attack={t: float(coef[2 + i]) for t, i in idx.items()},
        defence={t: float(coef[2 + k + i]) for t, i in idx.items()},
        ratings=ratings,
        mean_elo=float(np.mean(list(ratings.values()))) if ratings else 1500.0,
    )
