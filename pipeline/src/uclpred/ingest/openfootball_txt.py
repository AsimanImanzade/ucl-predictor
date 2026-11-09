"""Parser for openfootball Football.TXT European competition files."""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import requests

from uclpred.config import RAW
from uclpred.ingest.http_cache import get_cached

log = logging.getLogger(__name__)

EURO_FILES = {
    "cl": "uefa.cl",
    "clq": "uefa.clq",
    "el": "uefa.el",
    "elq": "uefa.elq",
    "conf": "uefa.ecl",
    "confq": "uefa.eclq",
}
BASE_URL = "https://raw.githubusercontent.com/openfootball/champions-league/master/{season}/{file}.txt"
FIRST_SEASON, LAST_SEASON = 2011, 2025  # start years: 2011-12 .. 2025-26

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
_DATE_RE = re.compile(r"^\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
_MATCH_RE = re.compile(
    r"^\s*(?:(?P<t>\d{1,2}:\d{2})\s+)?"
    r"(?P<h>.+?) \((?P<hc>[A-Z]{3})\)\s+v\s+(?P<a>.+?) \((?P<ac>[A-Z]{3})\)(?:\s+(?P<score>.+?))?\s*$"
)
_PEN_RE = re.compile(r"^(\d+)-(\d+) pen\. (\d+)-(\d+) a\.e\.t\.(?: \((\d+)-(\d+))?")
_AET_RE = re.compile(r"^(\d+)-(\d+) a\.e\.t\.(?: \((\d+)-(\d+))?")
_PLAIN_RE = re.compile(r"^(\d+)-(\d+)")


@dataclass
class RawMatch:
    # Kickoff times in the files are local CET/CEST; for M1 they are stored as given
    # (labelled UTC, no conversion). Date-level precision is all downstream needs.
    date: datetime
    stage: str
    home_name: str
    home_country: str
    away_name: str
    away_country: str
    home_goals: int | None
    away_goals: int | None
    et_home: int | None
    et_away: int | None
    pens_home: int | None
    pens_away: int | None
    neutral: bool


def _parse_score(score: str | None):
    """Return (home90, away90, et_home, et_away, pens_home, pens_away)."""
    none6 = (None,) * 6
    if not score:
        return none6
    score = score.strip()
    if m := _PEN_RE.match(score):
        pen_h, pen_a, et_h, et_a, h90, a90 = m.groups()
        r90 = (int(h90), int(a90)) if h90 is not None else (None, None)
        return (*r90, int(et_h), int(et_a), int(pen_h), int(pen_a))
    if m := _AET_RE.match(score):
        et_h, et_a, h90, a90 = m.groups()
        r90 = (int(h90), int(a90)) if h90 is not None else (None, None)
        return (*r90, int(et_h), int(et_a), None, None)
    if m := _PLAIN_RE.match(score):
        return int(m[1]), int(m[2]), None, None, None, None
    return none6


def parse_football_txt(text: str, season: str) -> list[RawMatch]:
    out: list[RawMatch] = []
    stage = ""
    year: int | None = None
    month = day = 0
    hh, mm = 12, 0
    seen_next = False
    start_year = int(season[:4])
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(("=", "#")):
            continue
        if s.startswith("▪"):
            stage = s.lstrip("▪").strip()
            continue
        if d := _DATE_RE.match(line):
            mon = _MONTHS[d[1]]
            # Season-anchored: Jan-Jun -> start+1, Sep-Dec -> start. Jul/Aug -> start+1
            # only once the file has produced a date in start+1 (season-end finals),
            # else start (qualifiers). Explicit years win.
            if d[3]:
                year = int(d[3])
            elif mon <= 6 or (mon <= 8 and seen_next):
                year = start_year + 1
            else:
                year = start_year
            seen_next = seen_next or year > start_year
            month, day = mon, int(d[2])
            hh, mm = 12, 0
            continue
        m = _MATCH_RE.match(line)
        if not m or year is None:
            continue
        if m["t"]:
            hh, mm = (int(x) for x in m["t"].split(":"))
        h90, a90, eth, eta, ph, pa = _parse_score(m["score"])
        out.append(RawMatch(
            date=datetime(year, month, day, hh, mm, tzinfo=UTC),
            stage=stage,
            home_name=m["h"].strip(), home_country=m["hc"],
            away_name=m["a"].strip(), away_country=m["ac"],
            home_goals=h90, away_goals=a90,
            et_home=eth, et_away=eta, pens_home=ph, pens_away=pa,
            neutral=stage in ("Final", "Finals, Final"),
        ))
    return out


def load_openfootball_euro(season: str) -> list[tuple[str, RawMatch]]:
    """Fetch (cached) and parse all European competition files for a season."""
    result: list[tuple[str, RawMatch]] = []
    failures: list[str] = []
    for code, fname in EURO_FILES.items():
        url = BASE_URL.format(season=season, file=fname)
        path = RAW / "openfootball" / season / f"{fname}.txt"
        try:
            raw = get_cached(url, path)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                continue
            status = e.response.status_code if e.response is not None else "?"
            failures.append(f"{season} {fname}.txt: HTTP {status}")
            log.warning("openfootball %s failed: %s", url, e)
            continue
        result.extend((code, m) for m in parse_football_txt(raw.decode("utf-8"), season))
    if failures:
        raise RuntimeError("openfootball fetch failures: " + "; ".join(failures))
    return result
