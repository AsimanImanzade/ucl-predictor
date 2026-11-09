import time
from datetime import UTC, datetime

import numpy as np
import pytest

from uclpred.elo import run_elo
from uclpred.matches import load_matches
from uclpred.models.baseline import fit_baseline
from uclpred.models.metrics import rps


def _outcome(hg, ag):
    return 0 if hg > ag else (1 if hg == ag else 2)


@pytest.mark.data
def test_baseline_beats_base_rate_on_2025_26_league_phase():
    matches = load_matches()
    elo = run_elo(matches)
    as_of = datetime(2025, 9, 1, tzinfo=UTC)
    t0 = time.time()
    model = fit_baseline(matches, elo, as_of)
    print(f"\nfit time {time.time() - t0:.1f}s")

    cl = matches[matches["competition"] == "uefa.cl"]
    test = cl[(cl["season"] == "2025-26") & (cl["stage"] == "LEAGUE_STAGE")]
    assert len(test) == 144
    assert (test["status"] == "FINISHED").all()

    probs = []
    for r in test.itertuples():
        lh, la = model.lambdas(r.home_id, r.away_id, "home")
        m = model.predict_match(r.home_id, r.away_id)
        assert np.isfinite([lh, la]).all()
        probs.append(
            (float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum()))
        )
    y = np.array([_outcome(r.home_goals, r.away_goals) for r in test.itertuples()])
    model_rps = rps(np.array(probs), y)

    hist = cl[
        (cl["status"] == "FINISHED") & cl["season"].between("2011-12", "2024-25")
    ]
    ho = np.array([_outcome(r.home_goals, r.away_goals) for r in hist.itertuples()])
    rates = np.bincount(ho, minlength=3) / len(ho)
    base_rps = rps(np.tile(rates, (len(y), 1)), y)

    print(f"base rates (H,D,A) {rates.round(4)}  n_hist={len(ho)}")
    print(f"model RPS {model_rps:.4f}  base-rate RPS {base_rps:.4f}")
    print(f"rho {model.rho:.4f}  home coef {model.coef_home:.4f}  elo coef {model.coef_elo:.4f}")
    assert model_rps < base_rps
