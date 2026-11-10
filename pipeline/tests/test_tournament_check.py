import math

import pytest

from uclpred.tournament_check import (
    actual_outcomes,
    actual_top8,
    choose_sigma,
    score_tournament,
    stage_distribution,
)


class FakeResolver:
    def resolve(self, country, name):
        return f"{country.lower()}-{name.lower()}"


def _m(stage, home, away, winner="HOME_TEAM"):
    return {
        "stage": stage,
        "homeTeam": {"id": home, "name": chr(64 + home)},
        "awayTeam": {"id": away, "name": chr(64 + away)},
        "score": {"winner": winner},
    }


# ids 1..12 = A..L
COUNTRY = {i: "ENG" for i in range(1, 13)}
FD = [
    _m("LEAGUE_STAGE", 1, 2), _m("LEAGUE_STAGE", 3, 4), _m("LEAGUE_STAGE", 5, 6),
    _m("LEAGUE_STAGE", 7, 8), _m("LEAGUE_STAGE", 9, 10), _m("LEAGUE_STAGE", 11, 12),
    _m("PLAYOFFS", 3, 4), _m("PLAYOFFS", 5, 6, "AWAY_TEAM"),
    _m("LAST_16", 1, 3), _m("LAST_16", 2, 6, "AWAY_TEAM"), _m("LAST_16", 7, 8),
    _m("LAST_16", 9, 10), _m("LAST_16", 11, 12),
    _m("QUARTER_FINALS", 1, 6), _m("QUARTER_FINALS", 7, 9),
    _m("SEMI_FINALS", 1, 7), _m("SEMI_FINALS", 11, 5),
    _m("FINAL", 1, 11, "AWAY_TEAM"),
]  # fmt: skip


def test_actual_outcomes_labels():
    got = actual_outcomes(FD, FakeResolver(), COUNTRY)
    lab = {k.split("-")[1]: v for k, v in got.items()}
    assert len(got) == 12
    assert lab["k"] == "winner"  # won the final as the away side
    assert lab["a"] == "final"
    assert lab["g"] == "sf" and lab["e"] == "sf"
    assert lab["f"] == "qf"  # playoff winner reached the QF
    assert lab["i"] == "qf"
    assert lab["b"] == "r16"  # top-8 team that lost in the R16
    assert lab["c"] == "r16"  # playoff winner, lost R16
    assert lab["d"] == "po"  # lost the play-off
    assert lab["h"] == "r16" and lab["j"] == "r16" and lab["l"] == "r16"
    assert set(lab.values()) <= {"out", "po", "r16", "qf", "sf", "final", "winner"}


def test_actual_outcomes_out_for_league_only_team():
    fd = [_m("LEAGUE_STAGE", 1, 2), _m("PLAYOFFS", 1, 2)]
    lab = actual_outcomes(fd + [_m("LEAGUE_STAGE", 3, 4)], FakeResolver(), COUNTRY)
    assert {k.split("-")[1]: v for k, v in lab.items()} == {
        "a": "po", "b": "po", "c": "out", "d": "out"
    }  # fmt: skip


def test_actual_top8_is_last16_without_playoffs():
    top = {t.split("-")[1] for t in actual_top8(FD, FakeResolver(), COUNTRY)}
    assert top == {"a", "b", "g", "h", "i", "j", "k", "l"}


def _team(out, po, top8, r16, qf, sf, fin, win, tid="x"):
    return {
        "teamId": tid, "out": out, "top8": top8, "top24": 1.0 - out,
        "reach": {"po": po, "r16": r16, "qf": qf, "sf": sf, "final": fin, "winner": win},
    }  # fmt: skip


def test_stage_distribution_hand_values():
    t = _team(out=0.3, po=0.4, top8=0.3, r16=0.5, qf=0.3, sf=0.2, fin=0.1, win=0.04)
    d = stage_distribution(t)
    assert d["out"] == pytest.approx(0.3)
    assert d["po"] == pytest.approx(0.4 - (0.5 - 0.3))
    assert d["r16"] == pytest.approx(0.2)
    assert d["qf"] == pytest.approx(0.1)
    assert d["sf"] == pytest.approx(0.1)
    assert d["final"] == pytest.approx(0.06)
    assert d["winner"] == pytest.approx(0.04)
    assert sum(d.values()) == pytest.approx(1.0)


def test_stage_distribution_clips_tiny_negatives():
    t = _team(out=0.5, po=0.2, top8=0.3, r16=0.5 + 1e-12, qf=0.1, sf=0.05, fin=0.02, win=0.01)
    d = stage_distribution(t)
    assert all(v >= 0 for v in d.values())
    assert sum(d.values()) == pytest.approx(1.0)


def test_stage_distribution_rejects_inconsistent():
    with pytest.raises(AssertionError):
        stage_distribution(_team(0.5, 0.2, 0.2, 0.4, 0.2, 0.1, 0.05, 0.01))


def test_score_tournament_three_team_toy():
    # A: predicted p(winner)=0.5; actual winner. B: p(out)=0.8; actual out. C: p(po)=0.0; actual po
    a = _team(out=0.0, po=0.0, top8=1.0, r16=1.0, qf=0.8, sf=0.6, fin=0.5, win=0.5, tid="A")
    b = _team(out=0.8, po=0.2, top8=0.0, r16=0.1, qf=0.0, sf=0.0, fin=0.0, win=0.0, tid="B")
    c = _team(out=0.5, po=0.5, top8=0.0, r16=0.0, qf=0.0, sf=0.0, fin=0.0, win=0.0, tid="C")
    actual = {"A": "winner", "B": "out", "C": "out"}
    got = score_tournament({"A": a, "B": b, "C": c}, actual, top8_ids={"A"})
    ll = (-math.log(0.5) - math.log(0.8) - math.log(0.5)) / 3
    assert got["stage_log_loss"] == pytest.approx(ll)
    # top8 truth: A=1 -> (1-1)^2, B=0 -> 0, C=0 -> 0
    assert got["brier_top8"] == pytest.approx(0.0)
    # top24 = 1 - out: A 1.0 vs 1, B 0.2 vs 0, C 0.5 vs 0
    assert got["brier_top24"] == pytest.approx((0.0 + 0.04 + 0.25) / 3)
    assert got["max_title_share"] == pytest.approx(0.5)


def test_score_tournament_epsilon_floor():
    a = _team(out=1.0, po=0.0, top8=0.0, r16=0.0, qf=0.0, sf=0.0, fin=0.0, win=0.0, tid="A")
    got = score_tournament({"A": a}, {"A": "winner"}, top8_ids=set())
    assert got["stage_log_loss"] == pytest.approx(-math.log(1e-6))


def test_choose_sigma_rule():
    assert choose_sigma({0: 1.00, 40: 1.004, 70: 1.002, 100: 1.009}) == 70
    assert choose_sigma({0: 1.00, 40: 0.95, 70: 0.99, 100: 0.97}) == 40
