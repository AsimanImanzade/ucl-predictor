import math

import numpy as np
import pandas as pd
import pytest

from uclpred.elo import expected_home
from uclpred.models.metrics import brier, calibration_table, league_gap, log_loss


def test_log_loss_perfect_is_clipped_zero():
    assert log_loss(np.array([[1.0, 0, 0]]), np.array([0])) == pytest.approx(0.0, abs=1e-9)


def test_log_loss_value():
    got = log_loss(np.array([[0.5, 0.25, 0.25]]), np.array([1]))
    assert got == pytest.approx(-math.log(0.25))


def test_log_loss_clips_zero_prob():
    got = log_loss(np.array([[1.0, 0, 0]]), np.array([1]), eps=1e-12)
    assert got == pytest.approx(-math.log(1e-12))


def test_brier_uniform():
    got = brier(np.array([[1 / 3] * 3]), np.array([0]))
    assert got == pytest.approx(4 / 9 + 1 / 9 + 1 / 9)


def test_calibration_table_bins():
    p = np.array([0.05, 0.15, 0.17, 1.0])
    won = np.array([0, 1, 0, 1])
    t = calibration_table(p, won, bins=10)
    assert list(t.columns) == ["bin_lo", "bin_hi", "n", "mean_pred", "observed"]
    assert len(t) == 10
    assert list(t["n"]) == [1, 2, 0, 0, 0, 0, 0, 0, 0, 1]
    assert t.loc[1, "observed"] == pytest.approx(0.5)
    assert t.loc[1, "mean_pred"] == pytest.approx(0.16)
    assert t.loc[0, "observed"] == 0.0
    assert t.loc[9, "observed"] == 1.0  # last bin closed at 1.0
    assert t.loc[9, "bin_hi"] == pytest.approx(1.0)
    assert math.isnan(t.loc[2, "mean_pred"]) and math.isnan(t.loc[2, "observed"])


def _row(mid, date, season, comp, h, a, hg, ag, neutral=False, status="FINISHED"):
    return {
        "match_id": mid, "date": pd.Timestamp(date, tz="UTC"), "season": season,
        "competition": comp, "home_id": h, "away_id": a, "home_goals": hg,
        "away_goals": ag, "neutral": neutral, "status": status,
    }  # fmt: skip


def test_league_gap_hand_computed():
    rows = [
        # 2018-19: before from_season, must be ignored
        _row("d0", "2018-09-01", "2018-19", "nl.1", "ned-mid", "x", 1, 0),
        _row("d0b", "2018-09-01", "2018-19", "en.1", "eng-big", "y", 1, 0),
        _row("e0", "2018-10-01", "2018-19", "uefa.cl", "ned-mid", "eng-big", 0, 3),
        # 2019-20 domestic labels (last domestic match wins)
        _row("d1", "2019-09-01", "2019-20", "nl.1", "ned-mid", "x", 1, 0),
        _row("d2", "2019-09-02", "2019-20", "en.1", "eng-big", "y", 1, 0),
        _row("d3", "2019-09-03", "2019-20", "en.1", "z", "eng-big", 1, 0),
        # European: mid at home wins; mid away draws
        _row("e1", "2019-10-01", "2019-20", "uefa.cl", "ned-mid", "eng-big", 2, 1),
        _row("e2", "2019-11-01", "2019-20", "uefa.el", "eng-big", "ned-mid", 1, 1),
        # unlabelled club: excluded
        _row("e3", "2019-12-01", "2019-20", "uefa.cl", "ned-mid", "aze-none", 1, 0),
    ]
    m = pd.DataFrame(rows)
    m["home_goals"] = m["home_goals"].astype("Int64")
    m["away_goals"] = m["away_goals"].astype("Int64")
    pre = pd.DataFrame({
        "match_id": [r["match_id"] for r in rows],
        "home_elo_pre": 1500.0, "away_elo_pre": 1500.0,
    })  # fmt: skip
    pre.loc[pre.match_id == "e1", ["home_elo_pre", "away_elo_pre"]] = [1600.0, 1700.0]
    pre.loc[pre.match_id == "e2", ["home_elo_pre", "away_elo_pre"]] = [1750.0, 1650.0]
    e1 = expected_home(1600.0, 1700.0, 60.0)
    e2 = expected_home(1750.0, 1650.0, 60.0)
    expected = ((1.0 - e1) + (e2 - 0.5)) / 2
    gap, n = league_gap(m, pre, home_adv=60.0)
    assert n == 2
    assert gap == pytest.approx(expected)


def test_league_gap_neutral_and_missing_pre():
    rows = [
        _row("d1", "2019-09-01", "2019-20", "nl.1", "ned-mid", "x", 1, 0),
        _row("d2", "2019-09-02", "2019-20", "en.1", "eng-big", "y", 1, 0),
        _row("e1", "2019-10-01", "2019-20", "uefa.cl", "ned-mid", "eng-big", 0, 1, neutral=True),
    ]
    m = pd.DataFrame(rows)
    pre = pd.DataFrame({"match_id": ["d1", "d2", "e1"], "home_elo_pre": 1500.0,
                        "away_elo_pre": 1500.0})  # fmt: skip
    gap, n = league_gap(m, pre, home_adv=60.0)
    assert n == 1 and gap == pytest.approx(0.0 - 0.5)
    with pytest.raises(ValueError):
        league_gap(m, pre[pre.match_id != "e1"], home_adv=60.0)


def _frame(rows, pre_map):
    m = pd.DataFrame(rows)
    m["home_goals"] = m["home_goals"].astype("Int64")
    m["away_goals"] = m["away_goals"].astype("Int64")
    pre = pd.DataFrame({
        "match_id": [r["match_id"] for r in rows],
        "home_elo_pre": [pre_map.get(r["match_id"], (1500.0, 1500.0))[0] for r in rows],
        "away_elo_pre": [pre_map.get(r["match_id"], (1500.0, 1500.0))[1] for r in rows],
    })  # fmt: skip
    return m, pre


def test_league_gap_labels_are_per_season():
    # ned-x: nl.1 (mid) in 2019-20, en.1 (Big-5) in 2020-21.
    rows = [
        _row("d1", "2019-09-01", "2019-20", "nl.1", "ned-x", "ned-y", 1, 0),
        _row("d2", "2019-09-02", "2019-20", "en.1", "eng-big", "eng-y", 1, 0),
        _row("d3", "2020-09-01", "2020-21", "en.1", "ned-x", "eng-z", 1, 0),
        _row("d4", "2020-09-02", "2020-21", "pt.1", "por-mid", "por-y", 1, 0),
        _row("d5", "2020-09-03", "2020-21", "en.1", "eng-big", "eng-y", 1, 0),
        # 2019-20: ned-x is mid, eng-big Big-5; mid home wins
        _row("e1", "2019-10-01", "2019-20", "uefa.cl", "ned-x", "eng-big", 2, 0),
        # 2020-21: ned-x is Big-5, por-mid mid; mid home draws
        _row("e2", "2020-10-01", "2020-21", "uefa.cl", "por-mid", "ned-x", 0, 0),
    ]
    m, pre = _frame(rows, {"e1": (1600.0, 1700.0), "e2": (1400.0, 1650.0)})
    e1 = expected_home(1600.0, 1700.0, 60.0)
    e2 = expected_home(1400.0, 1650.0, 60.0)
    gap, n = league_gap(m, pre, home_adv=60.0)
    assert n == 2
    assert gap == pytest.approx(((1.0 - e1) + (0.5 - e2)) / 2)


def test_league_gap_last_domestic_match_in_season_wins():
    # tur-x plays tr.1 then en.1 within 2019-20; rows deliberately out of date order.
    rows = [
        _row("d2", "2020-01-15", "2019-20", "en.1", "tur-x", "eng-y", 1, 0),
        _row("d1", "2019-09-01", "2019-20", "tr.1", "tur-x", "tur-y", 1, 0),
        _row("d3", "2019-09-02", "2019-20", "pt.1", "por-mid", "por-y", 1, 0),
        # tur-x is Big-5 (last), por-mid mid; por-mid is away and loses
        _row("e1", "2020-02-20", "2019-20", "uefa.el", "tur-x", "por-mid", 3, 0),
    ]
    m, pre = _frame(rows, {"e1": (1700.0, 1550.0)})
    e = expected_home(1700.0, 1550.0, 60.0)
    gap, n = league_gap(m, pre, home_adv=60.0)
    assert n == 1
    assert gap == pytest.approx(e - 1.0)  # home S=1, mid is away: E - S


def test_calibration_table_edge_values():
    p = np.array([0.0, 0.1, 0.2, 0.3])
    won = np.array([0, 1, 1, 0])
    t = calibration_table(p, won, bins=10)
    assert list(t["n"]) == [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]
    assert t.loc[0, "mean_pred"] == 0.0
    assert t.loc[1, "mean_pred"] == pytest.approx(0.1)
    assert t.loc[1, "observed"] == 1.0
    assert t.loc[2, "mean_pred"] == pytest.approx(0.2)
    assert t.loc[2, "observed"] == 1.0


def test_league_gap_to_season_cap():
    rows = [
        _row("d1", "2019-09-01", "2019-20", "nl.1", "ned-mid", "x", 1, 0),
        _row("d2", "2019-09-02", "2019-20", "en.1", "eng-big", "y", 1, 0),
        _row("d3", "2020-09-01", "2020-21", "nl.1", "ned-mid", "x", 1, 0),
        _row("d4", "2020-09-02", "2020-21", "en.1", "eng-big", "y", 1, 0),
        _row("e1", "2019-10-01", "2019-20", "uefa.cl", "ned-mid", "eng-big", 0, 1, neutral=True),
        _row("e2", "2020-10-01", "2020-21", "uefa.cl", "ned-mid", "eng-big", 1, 0, neutral=True),
    ]
    m = pd.DataFrame(rows)
    pre = pd.DataFrame({"match_id": m["match_id"], "home_elo_pre": 1500.0, "away_elo_pre": 1500.0})
    assert league_gap(m, pre, 60.0) == (pytest.approx(0.0), 2)
    gap, n = league_gap(m, pre, 60.0, to_season="2019-20")
    assert n == 1 and gap == pytest.approx(-0.5)
    gap, n = league_gap(m, pre, 60.0, from_season="2020-21", to_season="2020-21")
    assert n == 1 and gap == pytest.approx(0.5)
