from datetime import UTC, datetime

import pandas as pd
import pytest

from uclpred.ingest.football_data import FdMatch
from uclpred.ingest.openfootball_txt import RawMatch
from uclpred.matches import (
    MATCH_COLUMNS,
    combine,
    season_label,
    to_frame,
    validate_matches,
)
from uclpred.teams import TeamResolver


@pytest.fixture(scope="module")
def resolver():
    return TeamResolver()


def raw(home="Arsenal FC", away="Chelsea FC", hg=2, ag=1, day=1):
    return RawMatch(
        date=datetime(2025, 9, day, 19, tzinfo=UTC), stage="MD1",
        home_name=home, home_country="ENG", away_name=away, away_country="ENG",
        home_goals=hg, away_goals=ag, et_home=None, et_away=None,
        pens_home=None, pens_away=None, neutral=False,
    )  # fmt: skip


def fdm(status="FINISHED", hg=2, ag=1, fd_id=99):
    return FdMatch(
        date=datetime(2025, 9, 2, 19, tzinfo=UTC), stage="LEAGUE_STAGE",
        home_name="Arsenal FC", home_country="ENG", away_name="Chelsea FC", away_country="ENG",
        home_goals=hg, away_goals=ag, et_home=None, et_away=None,
        pens_home=None, pens_away=None, neutral=False,
        fd_id=fd_id, matchday=1, status=status, home_fd_id=57, away_fd_id=61,
        home_tla="ARS", away_tla="CHE", home_crest="", away_crest="",
    )  # fmt: skip


def test_season_label():
    assert season_label(2025) == "2025-26"
    assert season_label(1999) == "1999-00"


def test_openfootball_rows(resolver):
    df = to_frame([("uefa.cl", "2025-26", raw(), "openfootball"),
                   ("uefa.cl", "2025-26", raw(hg=None, ag=None, day=8), "openfootball")], resolver)  # fmt: skip
    assert list(df.columns) == MATCH_COLUMNS
    assert df.match_id[0] == f"of:uefa.cl:2025-09-01:{df.home_id[0]}:{df.away_id[0]}"
    assert list(df.status) == ["FINISHED", "SCHEDULED"]
    assert df.home_goals.dtype == "Int64" and pd.isna(df.home_goals[1])
    assert str(df.date.dt.tz) == "UTC"


def test_football_data_rows(resolver):
    df = to_frame([("uefa.cl", "2025-26", fdm(), "football-data"),
                   ("uefa.cl", "2025-26", fdm("AWARDED", fd_id=100), "football-data"),
                   ("uefa.cl", "2025-26", fdm("IN_PLAY", 1, 0, fd_id=101), "football-data"),
                   ("uefa.cl", "2025-26", fdm("TIMED", None, None, fd_id=102), "football-data")], resolver)  # fmt: skip
    assert list(df.match_id) == ["fd:99", "fd:100", "fd:101", "fd:102"]
    assert list(df.status) == ["FINISHED", "FINISHED", "SCHEDULED", "SCHEDULED"]
    assert pd.isna(df.home_goals[2]) and pd.isna(df.away_goals[2])
    assert (df.source == "football-data").all()


def test_combine_priority(resolver):
    a = to_frame([("uefa.cl", "2025-26", raw(), "openfootball"),
                  ("uefa.clq", "2025-26", raw(day=3), "openfootball")], resolver)  # fmt: skip
    b = to_frame([("uefa.cl", "2025-26", fdm(), "football-data")], resolver)
    out = combine([a, b])
    cl = out[out.competition == "uefa.cl"]
    assert list(cl.source) == ["football-data"]
    assert list(out[out.competition == "uefa.clq"].source) == ["openfootball"]
    assert out.date.is_monotonic_increasing


def good(resolver):
    return to_frame([("uefa.cl", "2025-26", raw(), "openfootball")], resolver)


def test_validate_ok(resolver):
    validate_matches(good(resolver))


def test_validate_flags_problems(resolver):
    df = to_frame([
        ("c", "s", raw(), "openfootball"),
        ("c", "s", raw(), "openfootball"),  # duplicate
        ("c", "s", raw(hg=-1, day=2), "openfootball"),
        ("c", "s", raw(away="Arsenal FC", day=3), "openfootball"),
    ], resolver)  # fmt: skip
    df.loc[3, "home_goals"] = pd.NA
    df.loc[3, "status"] = "FINISHED"
    with pytest.raises(ValueError) as e:
        validate_matches(df)
    msg = str(e.value)
    for needle in ("duplicate", "negative", "without goals", "plays itself"):
        assert needle in msg
