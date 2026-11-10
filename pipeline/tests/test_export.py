import copy
import json
import math
from types import SimpleNamespace
from datetime import UTC, datetime

import pytest

from uclpred.export import build_lambdas, build_season, validate_snapshot
from uclpred.models.baseline import BaselineModel
from uclpred.teams import TeamResolver

N = 36
AS_OF = datetime(2026, 9, 7, tzinfo=UTC)


def _fd_teams():
    return [
        {"id": 1000 + i, "name": f"Club{chr(65 + i // 6)}{chr(65 + i % 6)} FC",
         "shortName": f"C{i}", "tla": f"T{i:02d}", "crest": f"http://c/{i}.png",
         "area": {"code": "GER", "name": "Germany"}}
        for i in range(N)
    ]  # fmt: skip


def _fd_matches(status="SCHEDULED", date="2026-09-08T16:45:00Z"):
    """144 fixtures: each team plays 4 home and 4 away (i hosts i+1..i+4 mod 36)."""
    out, mid = [], 1
    for i in range(N):
        for k in range(1, 5):
            j = (i + k) % N
            out.append({
                "id": mid, "utcDate": date, "status": status, "matchday": k,
                "stage": "LEAGUE_STAGE",
                "homeTeam": {"id": 1000 + i, "name": f"H{i}"},
                "awayTeam": {"id": 1000 + j, "name": f"A{j}"},
                "score": {"duration": "REGULAR", "fullTime": {"home": 2, "away": 1}},
            })  # fmt: skip
            mid += 1
    return out


class FakeModel:
    rho = -0.05
    as_of = AS_OF

    def lambdas(self, a, b, venue):
        return (1.5 if venue == "home" else 1.3, 1.1)


def _season(matches=None, as_of=AS_OF):
    return build_season(
        matches or _fd_matches(), _fd_teams(), TeamResolver(), {}, as_of
    )


def _snapshot():
    season = _season()
    lam = build_lambdas(FakeModel(), [t["id"] for t in season["teams"]])
    return season, lam


def test_future_kickoff_finished_is_unplayed():
    s = _season(_fd_matches(status="FINISHED"))
    assert all(not f["played"] for f in s["fixtures"])
    assert all(f["homeGoals"] is None and f["awayGoals"] is None for f in s["fixtures"])


def test_finished_before_as_of_is_played():
    s = _season(_fd_matches(status="FINISHED"), as_of=datetime(2026, 9, 9, tzinfo=UTC))
    assert all(f["played"] for f in s["fixtures"])
    assert s["fixtures"][0]["homeGoals"] == 2 and s["fixtures"][0]["awayGoals"] == 1


def test_postponed_unplayed_but_counted():
    ms = _fd_matches(status="FINISHED", date="2026-09-01T16:45:00Z")
    ms[0]["status"] = "POSTPONED"
    s = _season(ms)
    assert len(s["fixtures"]) == 144
    assert s["fixtures"][0]["played"] is False
    assert s["fixtures"][0]["homeGoals"] is None
    assert sum(f["played"] for f in s["fixtures"]) == 143


def test_season_shape_and_ordering():
    s = _season()
    assert s["season"] == "2026-27"
    assert s["asOf"] == "2026-09-07T00:00:00Z"
    assert s["finalVenueTeamId"] == "esp-atletico-madrid"
    ids = [t["id"] for t in s["teams"]]
    assert ids == sorted(ids) and len(set(ids)) == N
    assert set(s["teams"][0]) == {
        "id",
        "fdId",
        "name",
        "shortName",
        "tla",
        "crest",
        "country",
        "coefficient",
    }
    assert s["teams"][0]["country"] == "GER"
    assert s["teams"][0]["coefficient"] == 0.0
    f = s["fixtures"][0]
    assert set(f) == {
        "id",
        "matchday",
        "utcDate",
        "homeId",
        "awayId",
        "played",
        "homeGoals",
        "awayGoals",
    }
    keys = [(f["utcDate"], f["id"]) for f in s["fixtures"]]
    assert keys == sorted(keys)


def test_non_league_stage_excluded():
    ms = _fd_matches()
    ms.append({**copy.deepcopy(ms[0]), "id": 999, "stage": "PLAYOFFS"})
    assert len(_season(ms)["fixtures"]) == 144


def test_coefficient_lookup():
    ids = [t["id"] for t in _season()["teams"]]
    s = build_season(_fd_matches(), _fd_teams(), TeamResolver(), {ids[0]: 12.5}, AS_OF)
    assert s["teams"][0]["coefficient"] == 12.5
    assert s["teams"][1]["coefficient"] == 0.0


def test_lambdas_shape():
    season, lam = _snapshot()
    assert lam["model"] == "elo-dc-v1"
    assert lam["asOf"] == season["asOf"]
    assert lam["rho"] == -0.05
    assert lam["teams"] == [t["id"] for t in season["teams"]]
    for key in ("home", "neutral"):
        m = lam[key]
        assert len(m) == N and all(len(r) == N for r in m)
        assert all(m[i][i] is None for i in range(N))
        assert m[0][1] == [1.5 if key == "home" else 1.3, 1.1]
    json.dumps(lam, allow_nan=False)


def test_validate_ok():
    validate_snapshot(*_snapshot())


def test_validate_rejects_143_fixtures():
    season, lam = _snapshot()
    season["fixtures"].pop()
    with pytest.raises(ValueError, match="144"):
        validate_snapshot(season, lam)


def test_validate_rejects_five_home_games():
    season, lam = _snapshot()
    f = next(f for f in season["fixtures"] if f["homeId"] != season["teams"][0]["id"])
    f["homeId"] = season["teams"][0]["id"]
    with pytest.raises(ValueError, match="home"):
        validate_snapshot(season, lam)


def test_validate_rejects_nan_lambda():
    season, lam = _snapshot()
    lam["home"][0][1] = [math.nan, 1.0]
    with pytest.raises(ValueError, match="lambda"):
        validate_snapshot(season, lam)


def test_validate_rejects_out_of_range_lambda():
    season, lam = _snapshot()
    lam["neutral"][2][3] = [0.01, 7.0]
    with pytest.raises(ValueError, match="lambda"):
        validate_snapshot(season, lam)


def test_validate_rejects_team_order_mismatch():
    season, lam = _snapshot()
    lam["teams"][0], lam["teams"][1] = lam["teams"][1], lam["teams"][0]
    with pytest.raises(ValueError, match="order"):
        validate_snapshot(season, lam)


def test_unseen_team_lambda_in_range():
    model = BaselineModel(
        as_of=AS_OF, rho=-0.05, mu=0.2, coef_home=0.25, coef_elo=0.1,
        attack={}, defence={}, ratings={"x": 1700.0}, mean_elo=1500.0,
    )  # fmt: skip
    lam = build_lambdas(model, ["x", "unseen"])
    for key in ("home", "neutral"):
        for a, b in lam[key][0][1], lam[key][1][0]:
            assert 0.05 <= a <= 6.0 and 0.05 <= b <= 6.0


def test_warn_unrated_teams(caplog):
    import logging

    from uclpred.export import warn_unrated_teams

    stub = SimpleNamespace(
        ratings={"a": 1500.0, "b": 1500.0}, attack={"a": 0.0, "c": 0.0}
    )
    with caplog.at_level(logging.WARNING, logger="uclpred.export"):
        bad = warn_unrated_teams(stub, ["a", "b", "c"])
    assert bad == ["b", "c"]
    msgs = [r.getMessage() for r in caplog.records]
    assert any("b" in m and "training window" in m for m in msgs)
    assert any("c" in m and "Elo" in m for m in msgs)
    assert not any("'a'" in m or " a " in m for m in msgs)
