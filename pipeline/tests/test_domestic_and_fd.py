import json
from pathlib import Path

import pytest
import requests

from uclpred.ingest import football_data, openfootball_json
from uclpred.ingest.football_data import FootballDataClient, normalize_fd_match
from uclpred.ingest.openfootball_json import load_football_json

FIX = Path(__file__).parent / "fixtures"
TEAM_COUNTRY = {109: "ITA", 610: "TUR", 524: "FRA", 57: "ENG", 77: "ESP"}


@pytest.fixture(scope="module")
def fd():
    ms = json.loads((FIX / "fd_matches_sample.json").read_text(encoding="utf-8"))["matches"]
    return {m["id"]: normalize_fd_match(m, TEAM_COUNTRY) for m in ms}


def test_regular(fd):
    m = fd[551981]
    assert (m.home_goals, m.away_goals) == (0, 2)
    assert m.et_home is None and m.pens_home is None
    assert m.status == "FINISHED" and not m.neutral
    assert m.home_fd_id == 77 and m.home_tla == "ATH" and m.home_crest.endswith("77.png")
    assert m.matchday == 1 and m.fd_id == 551981


def test_extra_time(fd):
    m = fd[552063]
    assert (m.home_goals, m.away_goals) == (3, 0)
    assert (m.et_home, m.et_away) == (3, 2)
    assert m.pens_home is None


def test_penalty_final(fd):
    m = fd[552096]
    assert (m.home_goals, m.away_goals) == (1, 1)
    assert (m.et_home, m.et_away) == (1, 1)
    assert (m.pens_home, m.pens_away) == (4, 3)
    assert m.stage == "FINAL" and m.neutral is True
    assert m.matchday is None


def test_postponed(fd):
    m = fd[999999]
    assert m.status == "POSTPONED"
    assert m.home_goals is None and m.away_goals is None and m.et_home is None


def test_country_mapping(fd):
    assert fd[552063].away_country == "TUR"
    assert fd[551981].home_country == "ESP"
    m = normalize_fd_match(
        json.loads((FIX / "fd_matches_sample.json").read_text())["matches"][0], {77: "DEU", 57: "NLD"}
    )
    assert (m.home_country, m.away_country) == ("GER", "NED")


def test_football_json(monkeypatch):
    body = (FIX / "ofjson_sample.json").read_bytes()
    seen = {}

    def fake(url, cache_path, headers=None, min_interval_s=0.0):
        seen["url"] = url
        return body

    monkeypatch.setattr(openfootball_json, "get_cached", fake)
    ms = load_football_json("2025-26", "tr.1")
    assert seen["url"].endswith("/2025-26/tr.1.json")
    assert len(ms) == 3
    assert ms[0].home_goals == 0 and ms[0].away_goals == 3
    assert ms[0].date.hour == 20 and ms[0].date.minute == 30 and ms[0].date.tzinfo is not None
    assert ms[0].away_name == "Galatasaray" and ms[0].away_country == "TUR"
    assert ms[0].home_country == "TUR" and ms[0].neutral is False
    assert ms[2].home_goals is None and ms[2].away_goals is None


def test_football_json_404_skipped(monkeypatch):
    def fake(url, cache_path, headers=None, min_interval_s=0.0):
        r = requests.Response()
        r.status_code = 404
        raise requests.HTTPError(response=r)

    monkeypatch.setattr(openfootball_json, "get_cached", fake)
    assert load_football_json("1999-00", "tr.1") == []


def test_football_json_500_raises(monkeypatch):
    def fake(url, cache_path, headers=None, min_interval_s=0.0):
        r = requests.Response()
        r.status_code = 500
        raise requests.HTTPError(response=r)

    monkeypatch.setattr(openfootball_json, "get_cached", fake)
    with pytest.raises(requests.HTTPError):
        load_football_json("2025-26", "tr.1")


class FakeResp:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code = status
        self.content = json.dumps(payload or {"matches": []}).encode()
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


def test_client_never_stores_token(monkeypatch, tmp_path):
    token = "SECRET-TOKEN-123"
    monkeypatch.setattr(football_data, "RAW", tmp_path)
    monkeypatch.setattr(football_data.time, "sleep", lambda s: None)
    sent = {}

    def fake_get(url, headers=None, timeout=None):
        sent["headers"] = headers
        return FakeResp(payload={"matches": [{"id": 1}], "teams": [{"id": 2}]})

    monkeypatch.setattr(requests, "get", fake_get)
    c = FootballDataClient(token)
    assert c.matches("CL", 2025) == [{"id": 1}]
    assert c.teams("CL", 2025) == [{"id": 2}]
    assert sent["headers"]["X-Auth-Token"] == token
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert len(files) == 2
    for p in files:
        assert token not in str(p)
        assert token not in p.read_text()
    assert {p.name for p in files} == {"CL_2025_matches.json", "CL_2025_teams.json"}


def test_client_403(monkeypatch, tmp_path):
    monkeypatch.setattr(football_data, "RAW", tmp_path)
    monkeypatch.setattr(football_data.time, "sleep", lambda s: None)
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(status=403))
    with pytest.raises(PermissionError):
        FootballDataClient("x").matches("CL", 2025)
