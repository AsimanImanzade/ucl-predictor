from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from uclpred.elo import EloParams, EloResult, expected_home, mov_multiplier, run_elo

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


def test_expected_home():
    assert expected_home(1500, 1500, 0) == 0.5
    assert expected_home(1500, 1500, 60) > 0.5


def test_mov_multiplier():
    assert mov_multiplier(0) == 1.0
    assert mov_multiplier(1) == 1.0
    assert mov_multiplier(-1) == 1.0
    assert mov_multiplier(2) == 1.5
    assert mov_multiplier(-2) == 1.5
    assert mov_multiplier(4) == 15 / 8


def test_draw_symmetric_and_conserved():
    p = EloParams()
    res = run_elo(frame([(0, "xx.1", "aaa-a", "bbb-b", 1, 1)]), p)
    exp = expected_home(p.init_top, p.init_top, p.home_adv)
    ra = res.rating_as_of("aaa-a", T0 + timedelta(days=1))
    rb = res.rating_as_of("bbb-b", T0 + timedelta(days=1))
    assert ra == pytest.approx(p.init_top + p.k * (0.5 - exp))
    assert rb == pytest.approx(p.init_top - p.k * (0.5 - exp))
    assert ra + rb == pytest.approx(2 * p.init_top)
    assert ra < p.init_top


def test_neutral_uses_zero_home_adv():
    res = run_elo(frame([(0, "xx.1", "aaa-a", "bbb-b", 1, 1, True)]))
    after = T0 + timedelta(days=1)
    assert res.rating_as_of("aaa-a", after) == pytest.approx(1500.0)
    assert res.rating_as_of("bbb-b", after) == pytest.approx(1500.0)


def test_point_in_time():
    rows = [
        (0, "xx.1", "aaa-a", "bbb-b", 3, 0),
        (10, "xx.1", "aaa-a", "bbb-b", 0, 2),
        (20, "xx.1", "bbb-b", "aaa-a", 1, 1),
    ]
    df = frame(rows)
    res = run_elo(df)
    assert res.rating_as_of("aaa-a", T0) is None  # strictly before first match
    assert res.rating_as_of("aaa-a", T0 - timedelta(days=5)) is None
    pre = res.pre.set_index("match_id")
    for _, m in df.iterrows():
        if m.date == df.date.min():
            continue
        assert pre.loc[m.match_id, "home_elo_pre"] == res.rating_as_of(m.home_id, m.date)
        assert pre.loc[m.match_id, "away_elo_pre"] == res.rating_as_of(m.away_id, m.date)
    # as_of exactly at kickoff excludes that match; a moment later includes it
    d1 = T0 + timedelta(days=10)
    before = res.rating_as_of("aaa-a", d1)
    after = res.rating_as_of("aaa-a", d1 + timedelta(seconds=1))
    assert before != after
    assert before == pre.loc["m001", "home_elo_pre"]
    assert after > 0 and set(res.ratings_as_of(d1)) == {"aaa-a", "bbb-b"}
    assert res.ratings_as_of(T0) == {}


def test_scheduled_ignored():
    df = frame([
        (0, "xx.1", "aaa-a", "bbb-b", 1, 0),
        (5, "xx.1", "aaa-a", "ccc-c", 0, 0, False, "SCHEDULED"),
    ])
    res = run_elo(df)
    assert len(res.pre) == 1
    assert res.rating_as_of("ccc-c", T0 + timedelta(days=30)) is None


def test_second_tier_seed():
    res = run_elo(frame([(0, "xx.2", "aaa-a", "bbb-b", 1, 1)]))
    assert res.pre.iloc[0].home_elo_pre == 1350.0


def _rated_league(n, comp="xx.1", base_goal=(1, 1)):
    # n distinct pairs in comp, each a draw -> teams rated near init
    rows = []
    for i in range(n):
        rows.append((i, comp, f"xxx-h{i}", f"xxx-a{i}", *base_goal, True))
    return rows


def test_top_tier_seed_uses_mean_with_five_rated():
    rows = _rated_league(3)  # 6 rated teams in xx.1
    # make ratings differ: a big win for h0 (neutral)
    rows[0] = (0, "xx.1", "xxx-h0", "xxx-a0", 5, 0, True)
    df = frame(rows + [(10, "xx.1", "new-t", "xxx-h1", 0, 0, True)])
    res = run_elo(df)
    at = T0 + timedelta(days=10)
    cur = [res.rating_as_of(t, at) for t in
           ["xxx-h0", "xxx-a0", "xxx-h1", "xxx-a1", "xxx-h2", "xxx-a2"]]
    assert res.pre.iloc[-1].home_elo_pre == pytest.approx(sum(cur) / 6)


def test_top_tier_seed_init_top_with_few_rated():
    df = frame(_rated_league(2) + [(10, "xx.1", "new-t", "xxx-h1", 0, 0, True)])  # 4 rated
    res = run_elo(df)
    assert res.pre.iloc[-1].home_elo_pre == 1500.0


def test_both_new_teams_seeded_symmetrically():
    rows = _rated_league(3)
    df = frame(rows + [(10, "xx.1", "new-a", "new-b", 0, 0, True)])
    res = run_elo(df)
    last = res.pre.iloc[-1]
    assert last.home_elo_pre == last.away_elo_pre


def test_uefa_seed_country_mean_else_unknown():
    rows = [
        (0, "xx.1", "esp-a", "esp-b", 1, 1, True),
        (1, "xx.1", "esp-c", "ger-x", 1, 1, True),
    ]
    # 3 spanish rated -> mean; ger has 1 -> unknown
    df = frame(rows + [
        (10, "uefa.cl", "esp-new", "ger-new", 0, 0, True),
        (11, "uefa.cl", "ita-new", "fra-new", 0, 0, True),
    ])
    res = run_elo(df)
    at = T0 + timedelta(days=10)
    mean = sum(res.rating_as_of(t, at) for t in ["esp-a", "esp-b", "esp-c"]) / 3
    pre = res.pre.set_index("match_id")
    assert pre.loc["m002", "home_elo_pre"] == pytest.approx(mean)
    assert pre.loc["m002", "away_elo_pre"] == 1400.0
    assert pre.loc["m003", "home_elo_pre"] == 1400.0


def test_same_timestamp_processed_sequentially_by_match_id():
    df = frame([
        (0, "xx.1", "aaa-a", "bbb-b", 2, 0, True),
        (0, "xx.1", "aaa-a", "ccc-c", 0, 1, True),
    ])
    res = run_elo(df)
    pre = res.pre.set_index("match_id")
    # second match's pre includes first match's result (same timestamp, later id)
    assert pre.loc["m001", "home_elo_pre"] > 1500.0
    assert isinstance(res, EloResult)
