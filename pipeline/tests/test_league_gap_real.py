import pytest

from uclpred.elo import run_elo
from uclpred.elo_v2 import EloV2Params, run_elo_v2
from uclpred.matches import load_matches
from uclpred.models.metrics import league_gap


@pytest.mark.data
def test_league_gap_v1_negative_v2_near_zero():
    matches = load_matches()
    g1, n1 = league_gap(matches, run_elo(matches).pre, home_adv=60.0)
    g2, n2 = league_gap(matches, run_elo_v2(matches, EloV2Params()).pre, home_adv=60.0)
    print(f"\nleague gap v1={g1:.4f} (n={n1})  v2={g2:.4f} (n={n2})")
    assert g1 < -0.10
    assert abs(g2) < 0.06
