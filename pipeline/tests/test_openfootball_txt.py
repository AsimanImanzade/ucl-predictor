from datetime import UTC, datetime
from pathlib import Path

import pytest
import requests

from uclpred.ingest import http_cache, openfootball_txt
from uclpred.ingest.openfootball_txt import parse_football_txt

FIXTURE = Path(__file__).parent / "fixtures" / "of_sample.txt"


@pytest.fixture(scope="module")
def matches():
    return parse_football_txt(FIXTURE.read_text(encoding="utf-8"), "2024-25")


def find(matches, home, away=None):
    out = [m for m in matches if m.home_name == home and (away is None or m.away_name == away)]
    assert len(out) == 1, out
    return out[0]


def test_match_count(matches):
    n = sum(1 for line in FIXTURE.read_text(encoding="utf-8").splitlines() if " v " in line)
    assert n == 21
    assert len(matches) == n


def test_young_boys(matches):
    m = find(matches, "BSC Young Boys")
    assert (m.home_goals, m.away_goals) == (0, 3)
    assert m.home_country == "SUI"
    assert m.away_name == "Aston Villa FC" and m.away_country == "ENG"
    assert m.date == datetime(2024, 9, 17, 18, 45, tzinfo=UTC)
    assert m.stage == "League, Matchday 1"


def test_time_inherited_and_year_inherited(matches):
    assert find(matches, "Juventus FC").date == datetime(2024, 9, 17, 18, 45, tzinfo=UTC)
    m = find(matches, "Bologna FC 1909")
    assert m.date == datetime(2024, 9, 18, 18, 45, tzinfo=UTC)
    assert find(matches, "AC Sparta Praha").date == datetime(2024, 9, 18, 18, 45, tzinfo=UTC)


def test_year_season_anchored_across_groups():
    text = (
        "▪ Group A\n  Tue Sep 17 2013\n    20:45  A FC (ENG)  v B FC (ESP)  1-0 (0-0)\n"
        "  Tue Dec 10\n    20:45  A FC (ENG)  v C FC (ESP)  1-0 (0-0)\n"
        "▪ Group B\n  Tue Sep 17\n    20:45  D FC (ENG)  v E FC (ESP)  1-0 (0-0)\n"
        "  Wed Feb 19\n    20:45  F FC (ENG)  v G FC (ESP)  1-0 (0-0)\n"
    )
    ms = parse_football_txt(text, "2013-14")
    assert [m.date.year for m in ms] == [2013, 2013, 2013, 2014]


def test_yearless_feb_is_next_year():
    text = "▪ X\n  Wed Feb 19\n    20:45  C FC (ENG)  v D FC (ESP)  1-0 (0-0)\n"
    assert parse_football_txt(text, "2013-14")[0].date == datetime(2014, 2, 19, 20, 45, tzinfo=UTC)


def test_aet_without_parens_has_no_90min_goals():
    text = "▪ X\n  Wed Feb 19\n    20:45  C FC (ENG)  v D FC (ESP)  2-1 a.e.t.\n"
    m = parse_football_txt(text, "2013-14")[0]
    assert m.home_goals is None and m.away_goals is None
    assert (m.et_home, m.et_away) == (2, 1)


def test_season_end_august_is_next_year():
    text = (
        "▪ Round of 16\n  Tue Mar 10\n    21:00  A FC (ENG)  v B FC (ESP)  1-0 (0-0)\n"
        "▪ Final\n  Fri Aug 7\n    21:00  C FC (ENG)  v D FC (ESP)  1-0 (0-0)\n"
    )
    ms = parse_football_txt(text, "2019-20")
    assert [m.date.date().isoformat() for m in ms] == ["2020-03-10", "2020-08-07"]


def test_qualifier_july_is_start_year():
    text = "▪ 1. Round\n  Tue Jul 8\n    19:00  A FC (ENG)  v B FC (ESP)  1-0 (0-0)\n"
    assert parse_football_txt(text, "2025-26")[0].date.date().isoformat() == "2025-07-08"


def test_default_time_is_noon():
    text = "▪ X\n  Tue Dec 10 2013\n    A FC (ENG)  v B FC (ESP)  1-0 (0-0)\n"
    assert parse_football_txt(text, "2013-14")[0].date == datetime(2013, 12, 10, 12, 0, tzinfo=UTC)


def test_extra_time(matches):
    m = find(matches, "Real Madrid", "Atlético Madrid")
    assert (m.home_goals, m.away_goals) == (1, 1)
    assert (m.et_home, m.et_away) == (4, 1)
    assert m.pens_home is None and m.pens_away is None


def test_penalties_with_ht(matches):
    m = find(matches, "AS Roma")
    assert (m.home_goals, m.away_goals) == (1, 1)
    assert (m.pens_home, m.pens_away) == (4, 2)
    assert (m.et_home, m.et_away) == (1, 1)


def test_penalties_short_ht(matches):
    m = find(matches, "FK Kairat")
    assert (m.home_goals, m.away_goals) == (0, 0)
    assert (m.pens_home, m.pens_away) == (3, 2)
    assert (m.et_home, m.et_away) == (0, 0)


def test_no_ht(matches):
    m = find(matches, "The New Saints")
    assert (m.home_goals, m.away_goals) == (0, 0)
    assert m.et_home is None and m.pens_home is None
    assert m.away_name == "KF Shkëndija 79"


def test_neutral(matches):
    assert find(matches, "Paris Saint-Germain FC", "FC Internazionale Milano").neutral is True
    assert find(matches, "Real Madrid").neutral is True
    assert find(matches, "BSC Young Boys").neutral is False
    assert find(matches, "AS Roma").neutral is False
    assert find(matches, "Manchester United").neutral is False


def test_unplayed_fixture():
    text = "▪ X\n  Tue Dec 10 2013\n    20:45  A FC (ENG)  v B FC (ESP)\n"
    m = parse_football_txt(text, "2013-14")[0]
    assert m.home_goals is None and m.away_goals is None


def test_get_cached_writes_and_reuses(tmp_path, monkeypatch):
    calls = []

    class R:
        status_code = 200
        content = b"hello"

        def raise_for_status(self):
            pass

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        return R()

    monkeypatch.setattr(http_cache.requests, "get", fake_get)
    p = tmp_path / "a" / "b" / "f.txt"
    assert http_cache.get_cached("http://x", p) == b"hello"
    assert http_cache.get_cached("http://x", p) == b"hello"
    assert len(calls) == 1 and p.read_bytes() == b"hello"


def test_get_cached_404_raises_http_error(tmp_path, monkeypatch):
    class R:
        status_code = 404
        content = b""

        def raise_for_status(self):
            raise requests.HTTPError("404", response=self)

    monkeypatch.setattr(http_cache.requests, "get", lambda *a, **k: R())
    with pytest.raises(requests.HTTPError):
        http_cache.get_cached("http://x", tmp_path / "f")
    assert not (tmp_path / "f").exists()


def _http_error(status):
    class R:
        status_code = status

    return requests.HTTPError(str(status), response=R())


def test_load_euro_skips_404_and_tags(monkeypatch):
    text = FIXTURE.read_bytes()

    def fake(url, path, **kw):
        if url.endswith("uefa.cl.txt"):
            return text
        raise _http_error(404)

    monkeypatch.setattr(openfootball_txt, "get_cached", fake)
    out = openfootball_txt.load_openfootball_euro("2024-25")
    assert len(out) == 21 and {c for c, _ in out} == {"cl"}


def test_load_euro_raises_after_loop_on_non_404(monkeypatch):
    seen = []

    def fake(url, path, **kw):
        seen.append(url)
        if url.endswith("uefa.el.txt"):
            raise _http_error(500)
        raise _http_error(404)

    monkeypatch.setattr(openfootball_txt, "get_cached", fake)
    with pytest.raises(RuntimeError, match=r"2024-25 uefa\.el\.txt: HTTP 500"):
        openfootball_txt.load_openfootball_euro("2024-25")
    assert len(seen) == len(openfootball_txt.EURO_FILES)
