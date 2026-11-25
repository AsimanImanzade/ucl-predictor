"""football-data client: same-day cache, force refresh, 429 retry, safe errors."""

import json
import traceback

import pytest
import requests

from uclpred.ingest import football_data, http_cache
from uclpred.ingest.football_data import FootballDataClient, FootballDataError

TOKEN = "SECRET-TOKEN-123"


class Resp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self.content = body if isinstance(body, bytes) else json.dumps(body or {"matches": []}).encode()
        self.headers = requests.structures.CaseInsensitiveDict(headers or {})


@pytest.fixture
def env(monkeypatch, tmp_path):
    sleeps: list[float] = []
    monkeypatch.setattr(football_data, "RAW", tmp_path)
    monkeypatch.setattr(football_data.time, "sleep", sleeps.append)
    return tmp_path, sleeps


def _serve(monkeypatch, responses):
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(requests, "get", fake_get)
    return calls


def _cache_files(root):
    return [p for p in root.rglob("*") if p.is_file()]


def test_same_day_cache_reused_unless_forced(monkeypatch, env):
    root, _ = env
    calls = _serve(monkeypatch, [Resp(body={"matches": [{"id": 1}]}), Resp(body={"matches": [{"id": 2}]})])
    assert FootballDataClient(TOKEN).matches("CL", 2026) == [{"id": 1}]
    assert FootballDataClient(TOKEN).matches("CL", 2026) == [{"id": 1}]  # cached
    assert len(calls) == 1
    assert FootballDataClient(TOKEN, force=True).matches("CL", 2026) == [{"id": 2}]
    assert len(calls) == 2
    (f,) = _cache_files(root)
    assert json.loads(f.read_text()) == {"matches": [{"id": 2}]}  # overwritten


def test_429_retried_after_reset(monkeypatch, env):
    _, sleeps = env
    _serve(monkeypatch, [Resp(429, headers={"X-RequestCounter-Reset": "17"}), Resp(body={"matches": [{"id": 3}]})])
    assert FootballDataClient(TOKEN).matches("CL", 2026) == [{"id": 3}]
    assert 17.0 in sleeps


def test_429_gives_up(monkeypatch, env):
    root, _ = env
    _serve(monkeypatch, [Resp(429) for _ in range(10)])
    with pytest.raises(FootballDataError, match="429"):
        FootballDataClient(TOKEN).matches("CL", 2026)
    assert _cache_files(root) == []


def test_sleeps_when_minute_quota_is_used_up(monkeypatch, env):
    _, sleeps = env
    _serve(monkeypatch, [Resp(headers={"x-requests-available-minute": "0", "X-RequestCounter-Reset": "42"})])
    FootballDataClient(TOKEN).matches("CL", 2026)
    assert 42.0 in sleeps


def test_invalid_json_not_cached(monkeypatch, env):
    root, _ = env
    _serve(monkeypatch, [Resp(body=b"<html>oops</html>")])
    with pytest.raises(FootballDataError, match="JSON"):
        FootballDataClient(TOKEN).matches("CL", 2026)
    assert _cache_files(root) == []


def test_missing_key_not_cached(monkeypatch, env):
    root, _ = env
    _serve(monkeypatch, [Resp(body={"message": "x"})])
    with pytest.raises(FootballDataError, match="matches"):
        FootballDataClient(TOKEN).matches("CL", 2026)
    assert _cache_files(root) == []


def _assert_no_token(exc: BaseException):
    text = "".join(traceback.format_exception(exc)) + repr(exc) + str(exc.args)
    assert TOKEN not in text
    assert exc.__cause__ is None and (exc.__context__ is None or exc.__suppress_context__)


def test_connection_error_hides_token(monkeypatch, env):
    req = requests.Request("GET", "https://x", headers={"X-Auth-Token": TOKEN}).prepare()
    _serve(monkeypatch, [requests.ConnectionError("boom", request=req)])
    with pytest.raises(FootballDataError) as ei:
        FootballDataClient(TOKEN).matches("CL", 2026)
    _assert_no_token(ei.value)


def test_server_error_hides_token(monkeypatch, env):
    _serve(monkeypatch, [Resp(500)])
    with pytest.raises(FootballDataError, match="500") as ei:
        FootballDataClient(TOKEN).matches("CL", 2026)
    _assert_no_token(ei.value)


def test_get_cached_atomic_write_leaves_no_temp(monkeypatch, tmp_path):
    class R:
        content = b"hello"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    out = tmp_path / "a" / "b.txt"
    assert http_cache.get_cached("https://x", out) == b"hello"
    assert [p.name for p in out.parent.iterdir()] == ["b.txt"]
