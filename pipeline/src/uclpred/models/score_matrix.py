"""Scoreline probability matrix: independent Poisson + Dixon-Coles low-score correction."""

import numpy as np
from scipy.stats import poisson


def tau(hg: int, ag: int, lh: float, la: float, rho: float) -> float:
    """Dixon-Coles correction factor for a single scoreline."""
    if hg == 0 and ag == 0:
        return 1 - lh * la * rho
    if hg == 0 and ag == 1:
        return 1 + lh * rho
    if hg == 1 and ag == 0:
        return 1 + la * rho
    if hg == 1 and ag == 1:
        return 1 - rho
    return 1.0


def score_matrix(lh: float, la: float, rho: float, max_goals: int = 10) -> np.ndarray:
    """P[i, j] = P(home scores i, away scores j), i, j in 0..max_goals, sums to 1."""
    k = np.arange(max_goals + 1)
    m = np.outer(poisson.pmf(k, lh), poisson.pmf(k, la))
    m[0, 0] *= tau(0, 0, lh, la, rho)
    m[0, 1] *= tau(0, 1, lh, la, rho)
    m[1, 0] *= tau(1, 0, lh, la, rho)
    m[1, 1] *= tau(1, 1, lh, la, rho)
    m = np.clip(m, 0.0, None)  # large lh*la*rho can push a cell negative
    return m / m.sum()


def outcome_probs(m: np.ndarray) -> tuple[float, float, float]:
    """(home win, draw, away win) from a score matrix."""
    home = float(np.tril(m, -1).sum())
    draw = float(np.trace(m))
    away = float(np.triu(m, 1).sum())
    return home, draw, away
