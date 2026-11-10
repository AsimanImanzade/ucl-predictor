from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from uclpred.elo import EloResult, expected_home, mov_multiplier
from uclpred.elo_v2 import EloV2Params, run_elo_v2

T0 = datetime(2020, 1, 1, tzinfo=UTC)


def frame(rows):
    """rows: (day_offset, comp, home, away, hg, ag[, neutral[, status]])"""
    recs = []
    for i, r in enumerate(rows):
        day, comp, h, a, hg, ag = r[:6]
        neutral = r[6] if len(r) > 6 else False
        status = r[7] if len(r) > 7 else "FINISHED"
        recs.append({
            "match_id": f"m{i:03d}", "date": T0 + timedelta(days=day),
            "season": "2019-20", "competition": comp, "stage": "x",
            "home_id": h, "away_id": a,
            "home_goals": hg if status == "FINISHED" else None,
            "away_goals": ag if status == "FINISHED" else None,
            "neutral": neutral, "status": status, "source": "t",
        })  # fmt: skip
    df = pd.DataFrame(recs)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["home_goals"] = df["home_goals"].astype("Int64")
    df["away_goals"] = df["away_goals"].astype("Int64")
    return df


def d(n):
    return T0 + timedelta(days=n)


P = EloV2Params()


def test_returns_elo_result():
    res = run_elo_v2(frame([(0, "aaa.1", "aaa-a", "aaa-b", 1, 0)]))
    assert isinstance(res, EloResult)
    assert list(res.pre.columns) == ["match_id", "home_elo_pre", "away_elo_pre"]


def test_domestic_match_never_moves_league_level():
    rows = [(0, "aaa.1", "aaa-a", "aaa-b", 3, 0), (1, "bbb.1", "bbb-a", "bbb-b", 0, 2)]
    res = run_elo_v2(frame(rows))
    before = res.league_levels_as_of(d(1) - timedelta(hours=1))
    after = res.league_levels_as_of(d(10))
    assert before["aaa.1"] == 1500.0
    assert after == {"aaa.1": 1500.0, "bbb.1": 1500.0}
    # offsets did move
    assert res.rating_as_of("aaa-a", d(10)) > 1500.0


def test_cross_league_euro_match_moves_levels_by_g():
    rows = [
        (0, "aaa.1", "aaa-a", "aaa-x", 1, 1),
        (0, "bbb.1", "bbb-a", "bbb-x", 1, 1),
        (10, "uefa.cl", "aaa-a", "bbb-a", 2, 0),
    ]
    res = run_elo_v2(frame(rows))
    ra0 = res.rating_as_of("aaa-a", d(5))
    rb0 = res.rating_as_of("bbb-a", d(5))
    exp = expected_home(ra0, rb0, P.home_adv)
    delta = P.k * P.k_euro * mov_multiplier(2) * (1.0 - exp)
    lv0 = res.league_levels_as_of(d(5))
    lv1 = res.league_levels_as_of(d(20))
    assert lv1["aaa.1"] - lv0["aaa.1"] == pytest.approx(P.g * delta)
    assert lv1["bbb.1"] - lv0["bbb.1"] == pytest.approx(-P.g * delta)
    assert res.rating_as_of("aaa-a", d(20)) - ra0 == pytest.approx(delta)
    assert res.rating_as_of("bbb-a", d(20)) - rb0 == pytest.approx(-delta)
    # a club that did not play shifts with its league level
    assert res.rating_as_of("aaa-x", d(20)) - res.rating_as_of(
        "aaa-x", d(5)
    ) == pytest.approx(P.g * delta)
    assert res.ratings_as_of(d(20))["bbb-x"] == pytest.approx(
        res.rating_as_of("bbb-x", d(5)) - P.g * delta
    )


def test_same_league_euro_match_moves_offsets_only():
    rows = [
        (0, "aaa.1", "aaa-a", "aaa-b", 1, 1),
        (10, "uefa.cl", "aaa-a", "aaa-b", 3, 0),
    ]
    res = run_elo_v2(frame(rows))
    lv0 = res.league_levels_as_of(d(5))
    lv1 = res.league_levels_as_of(d(20))
    assert lv0 == lv1
    ra0 = res.rating_as_of("aaa-a", d(5))
    rb0 = res.rating_as_of("aaa-b", d(5))
    delta = (
        P.k * P.k_euro * mov_multiplier(3) * (1.0 - expected_home(ra0, rb0, P.home_adv))
    )
    assert res.rating_as_of("aaa-a", d(20)) == pytest.approx(ra0 + delta)
    assert res.rating_as_of("aaa-b", d(20)) == pytest.approx(rb0 - delta)


def test_promotion_keeps_total_rating():
    rows = [
        (0, "aaa.2", "aaa-p", "aaa-q", 4, 0),
        (5, "aaa.2", "aaa-p", "aaa-q", 2, 0),
        (400, "aaa.1", "aaa-p", "aaa-r", 1, 0),
    ]
    res = run_elo_v2(frame(rows))
    last_after = res.rating_as_of("aaa-p", d(300))
    first_pre = res.pre.iloc[2]["home_elo_pre"]
    assert first_pre == pytest.approx(last_after, abs=1e-9)
    assert last_after != pytest.approx(1350.0)
    # promotion seeded aaa.1 at 1500 (fewer than 3 peers... aaa-p, aaa-q only)
    assert res.league_levels_as_of(d(500))["aaa.1"] == 1500.0
    assert res.league_levels_as_of(d(500))["aaa.2"] == 1350.0
    # new club aaa-r starts at the league level
    assert res.pre.iloc[2]["away_elo_pre"] == pytest.approx(1500.0)


def test_euro_history_then_first_domestic_keeps_total():
    rows = [
        (0, "uefa.clq", "aaa-e", "bbb-e", 3, 0),
        (10, "uefa.clq", "aaa-e", "bbb-e", 2, 0),
        (100, "aaa.1", "aaa-e", "aaa-f", 2, 1),
    ]
    res = run_elo_v2(frame(rows))
    assert res.pre.iloc[2]["home_elo_pre"] == pytest.approx(
        res.rating_as_of("aaa-e", d(50))
    )
    assert res.pre.iloc[0]["home_elo_pre"] == 1400.0  # seeded in pseudo-league aaa.x
    assert "aaa.1" in res.league_levels_as_of(d(200))


def test_euro_only_club_uses_country_pseudo_league():
    rows = [
        (0, "uefa.clq", "zzz-a", "yyy-a", 1, 0),
        (1, "uefa.clq", "zzz-b", "yyy-b", 1, 0),
        (2, "uefa.clq", "zzz-a", "zzz-b", 1, 1),
    ]
    res = run_elo_v2(frame(rows))
    lv = res.league_levels_as_of(d(10))
    assert "zzz.x" in lv and "yyy.x" in lv
    assert not any(k.startswith("zzz.") and k != "zzz.x" for k in lv)
    # zzz-a vs zzz-b: same pseudo-league so the 3rd match moves offsets only
    assert res.league_levels_as_of(
        d(2) + timedelta(hours=1)
    ) == res.league_levels_as_of(d(10))


def test_new_league_seeded_from_country_peers():
    # four aaa clubs rated via european matches (pseudo-league), then aaa.1 begins
    rows = [
        (0, "uefa.clq", "aaa-1", "bbb-1", 2, 0),
        (1, "uefa.clq", "aaa-2", "bbb-2", 0, 1),
        (2, "uefa.clq", "aaa-3", "bbb-3", 1, 0),
        (3, "uefa.clq", "aaa-4", "bbb-4", 3, 1),
        (50, "aaa.1", "aaa-1", "aaa-2", 1, 0),
    ]
    res = run_elo_v2(frame(rows))
    peers = ["aaa-1", "aaa-2", "aaa-3", "aaa-4"]
    mean = sum(res.rating_as_of(t, d(40)) for t in peers) / 4
    assert res.league_levels_as_of(d(60))["aaa.1"] == pytest.approx(mean)
    # fewer than 3 peers: defaults
    few = run_elo_v2(
        frame(
            [
                (0, "uefa.clq", "aaa-5", "bbb-1", 1, 0),
                (1, "aaa.1", "aaa-1", "aaa-2", 1, 0),
            ]
        )
    )
    assert few.league_levels_as_of(d(10))["aaa.1"] == 1500.0
    two = run_elo_v2(frame([(0, "aaa.2", "aaa-3", "aaa-4", 1, 0)]))
    assert two.league_levels_as_of(d(10))["aaa.2"] == 1350.0


def test_seeding_never_mixes_divisions():
    # three aaa clubs in aaa.2 only: they must not seed a new aaa.1 level
    rows = [
        (0, "aaa.2", "aaa-1", "aaa-2", 1, 0),
        (1, "aaa.2", "aaa-3", "aaa-2", 1, 0),
        (2, "aaa.1", "aaa-9", "aaa-8", 1, 0),
    ]
    res = run_elo_v2(frame(rows))
    assert res.league_levels_as_of(d(10))["aaa.1"] == 1500.0
    # a new .2 level is the .1/.x peer mean minus (init_top - init_second)
    rows = [
        (0, "aaa.1", "aaa-1", "aaa-2", 2, 0),
        (1, "aaa.1", "aaa-3", "aaa-4", 0, 1),
        (50, "aaa.2", "aaa-5", "aaa-6", 1, 0),
    ]
    res = run_elo_v2(frame(rows))
    mean = sum(res.rating_as_of(f"aaa-{i}", d(40)) for i in (1, 2, 3, 4)) / 4
    assert res.league_levels_as_of(d(60))["aaa.2"] == pytest.approx(mean - 150.0)


def test_same_kickoff_matches_use_group_snapshot():
    rows = [
        (0, "aaa.1", "aaa-a", "aaa-b", 1, 1),
        (0, "aaa.1", "aaa-c", "aaa-d", 1, 1),
        (0, "bbb.1", "bbb-a", "bbb-b", 1, 1),
        (10, "uefa.cl", "aaa-a", "bbb-a", 3, 0),
        (10, "uefa.cl", "bbb-b", "aaa-b", 0, 2),
        (10, "aaa.1", "aaa-c", "aaa-d", 2, 0),
    ]
    df = frame(rows)
    res = run_elo_v2(df)
    for _, row in df.iterrows():
        pre = res.pre[res.pre["match_id"] == row["match_id"]].iloc[0]
        for team, col in (
            (row["home_id"], "home_elo_pre"),
            (row["away_id"], "away_elo_pre"),
        ):
            r = res.rating_as_of(team, row["date"])
            if r is not None:
                assert pre[col] == pytest.approx(r, abs=1e-9)
    # aaa-d did not play in the cl matches but shares the moved league level
    assert res.rating_as_of("aaa-d", d(20)) != pytest.approx(
        res.rating_as_of("aaa-d", d(5))
    )


def test_k_euro_multiplier():
    base = [(0, "aaa.1", "aaa-a", "bbb-a", 2, 1)]
    dom = run_elo_v2(frame([(0, "xx.1", "aaa-a", "aaa-b", 2, 1)]))
    cl = run_elo_v2(frame([(0, "uefa.el", "aaa-a", "aaa-b", 2, 1)]))
    # both clubs new; euro puts them in aaa.x (1400) vs xx.1 -> aaa clubs in 'xx.1' (1500)
    dd = dom.rating_as_of("aaa-a", d(1)) - 1500.0
    de = cl.rating_as_of("aaa-a", d(1)) - 1400.0
    assert de == pytest.approx(P.k_euro * dd)
    assert base  # keep lint quiet about unused


def test_neutral_zero_home_advantage():
    res = run_elo_v2(frame([(0, "aaa.1", "aaa-a", "aaa-b", 1, 0, True)]))
    assert res.rating_as_of("aaa-a", d(1)) == pytest.approx(1500.0 + P.k * 0.5)


def test_point_in_time_pre_equals_rating_as_of():
    rows = [
        (0, "aaa.1", "aaa-a", "aaa-b", 2, 0),
        (3, "uefa.cl", "aaa-a", "bbb-a", 1, 1),
        (6, "bbb.2", "bbb-a", "bbb-c", 0, 2),
        (9, "bbb.1", "bbb-a", "bbb-b", 1, 0),
        (12, "uefa.cl", "bbb-b", "aaa-b", 0, 1),
        (15, "aaa.1", "aaa-a", "aaa-b", 2, 2),
        (16, "aaa.1", "aaa-b", "aaa-a", 2, 2, False, "SCHEDULED"),
    ]
    df = frame(rows)
    res = run_elo_v2(df)
    assert len(res.pre) == 6  # scheduled ignored
    fin = df[df["status"] == "FINISHED"].reset_index(drop=True)
    for i, row in fin.iterrows():
        pre = res.pre.iloc[i]
        assert pre["match_id"] == row["match_id"]
        for team, col in (
            (row["home_id"], "home_elo_pre"),
            (row["away_id"], "away_elo_pre"),
        ):
            r = res.rating_as_of(team, row["date"])
            if r is not None:
                assert pre[col] == pytest.approx(r, abs=1e-9)
    assert res.rating_as_of("aaa-a", d(0)) is None
    assert set(res.ratings_as_of(d(100))) == {
        "aaa-a",
        "aaa-b",
        "bbb-a",
        "bbb-b",
        "bbb-c",
    }
