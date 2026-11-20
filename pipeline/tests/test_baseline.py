from datetime import timedelta

import numpy as np
from test_elo import T0, frame

from uclpred.elo import run_elo
from uclpred.models.baseline import fit_baseline

AS_OF = T0 + timedelta(days=400)


def league(extra=()):
    rows = []
    day = 0
    teams = ["A", "B", "C", "D"]
    rng = np.random.default_rng(0)
    strength = {"A": 0.5, "B": 0.0, "C": 0.0, "D": -0.5}  # real Elo signal
    for _ in range(12):
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                if (h, a) == ("A", "B"):
                    hg, ag = 3, 0
                else:
                    d = strength[h] - strength[a]
                    hg, ag = int(rng.poisson(1.4 * np.exp(d))), int(rng.poisson(1.1 * np.exp(-d)))
                rows.append((day, "en.1", h, a, hg, ag))
                day += 1
    rows += list(extra)
    return frame(rows)


def test_a_beats_b_lambdas_and_elo_effect():
    m = league()
    elo = run_elo(m)
    model = fit_baseline(m, elo, AS_OF)
    la, lb = model.lambdas("A", "B", "neutral")
    assert la > lb
    assert -0.25 <= model.rho <= 0.25
    p = model.predict_match("A", "B")
    assert p.shape == (11, 11) and abs(p.sum() - 1) < 1e-9
    # raising A's Elo raises λ_A (same fit, bumped rating)
    base = model.lambdas("A", "C", "neutral")[0]
    model.ratings["A"] += 200
    assert model.lambdas("A", "C", "neutral")[0] > base


def test_home_advantage_and_unseen_team_finite():
    m = league()
    model = fit_baseline(m, run_elo(m), AS_OF)
    assert model.lambdas("C", "D", "home")[0] > model.lambdas("C", "D", "neutral")[0]
    la, lb = model.lambdas("ZZZ", "A", "neutral")
    assert np.isfinite(la) and np.isfinite(lb) and la > 0 and lb > 0


def test_leak_match_at_as_of_changes_nothing():
    base = league()
    leak = league(extra=[(400, "en.1", "A", "B", 20, 0)])
    # as_of exactly the leak match's kickoff
    as_of = T0 + timedelta(days=400)
    m1 = fit_baseline(base, run_elo(base), as_of)
    m2 = fit_baseline(leak, run_elo(leak), as_of)
    assert m1.rho == m2.rho
    assert np.allclose(m1.lambdas("A", "B", "home"), m2.lambdas("A", "B", "home"))
    assert m1.coef_home == m2.coef_home and m1.coef_elo == m2.coef_elo
