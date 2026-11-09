import numpy as np
from scipy.stats import poisson

from uclpred.models.metrics import rps
from uclpred.models.score_matrix import outcome_probs, score_matrix

# Shared with the TypeScript port (Task 10): outcome_probs(score_matrix(1.5, 1.1, -0.1)), 6 dp.
GOLDEN_OUTCOME = (0.451989, 0.282178, 0.265834)  # (home, draw, away)


def test_sums_to_one_and_shape():
    m = score_matrix(1.5, 1.1, 0.0)
    assert m.shape == (11, 11)
    assert abs(m.sum() - 1) < 1e-12


def test_rho_zero_is_independent_poisson():
    m = score_matrix(1.5, 1.1, 0.0)
    raw = poisson(1.5).pmf(2) * poisson(1.1).pmf(1)
    full = np.outer(poisson(1.5).pmf(np.arange(11)), poisson(1.1).pmf(np.arange(11))).sum()
    assert abs(m[2, 1] - raw / full) < 1e-12


def test_negative_rho_raises_00_and_11():
    a, b = score_matrix(1.5, 1.1, 0.0), score_matrix(1.5, 1.1, -0.1)
    assert b[0, 0] > a[0, 0] and b[1, 1] > a[1, 1]


def test_extreme_rho_clips_negative_cells():
    m = score_matrix(3.0, 3.0, 0.25)  # 1 - 9*0.25 < 0 before clipping
    assert (m >= 0).all() and abs(m.sum() - 1) < 1e-12


def test_golden_outcome():
    got = tuple(round(x, 6) for x in outcome_probs(score_matrix(1.5, 1.1, -0.1)))
    assert got == GOLDEN_OUTCOME


def test_rps():
    assert rps(np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]]), np.array([0, 1, 2])) == 0
    assert abs(rps(np.array([[1 / 3] * 3]), np.array([0])) - 0.2777778) < 1e-6
