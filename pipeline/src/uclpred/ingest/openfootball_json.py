"""Loader for openfootball football.json domestic league files."""

import json
import logging
from datetime import UTC, datetime

import requests

from uclpred.config import RAW
from uclpred.ingest.http_cache import get_cached
from uclpred.ingest.openfootball_txt import RawMatch
from uclpred.teams import LEAGUE_COUNTRY

log = logging.getLogger(__name__)

BASE_URL = "https://raw.githubusercontent.com/openfootball/football.json/master/{season}/{code}.json"
DOMESTIC_CODES = [
    "en.1", "en.2", "de.1", "de.2", "es.1", "es.2", "fr.1", "fr.2", "it.1", "it.2",
    "nl.1", "pt.1", "at.1", "be.1", "gr.1", "tr.1", "sco.1",
]  # fmt: skip


def _parse(data: dict, country: str) -> list[RawMatch]:
    out = []
    for m in data.get("matches", []):
        hh, mm = (m.get("time") or "12:00").split(":")[:2]
        y, mo, d = (int(x) for x in m["date"].split("-"))
        # Times are as given (local), labelled UTC, like the TXT parser.
        date = datetime(y, mo, d, int(hh), int(mm), tzinfo=UTC)
        ft = (m.get("score") or {}).get("ft")
        hg, ag = (ft[0], ft[1]) if ft else (None, None)
        out.append(
            RawMatch(
                date=date,
                stage=str(m.get("round", "")),
                home_name=m["team1"],
                home_country=country,
                away_name=m["team2"],
                away_country=country,
                home_goals=hg,
                away_goals=ag,
                et_home=None,
                et_away=None,
                pens_home=None,
                pens_away=None,
                neutral=False,
            )
        )
    return out


def load_football_json(season: str, code: str) -> list[RawMatch]:
    """Load one league-season; a missing file (404) yields an empty list."""
    country = LEAGUE_COUNTRY[code.split(".")[0]]
    url = BASE_URL.format(season=season, code=code)
    cache = RAW / "openfootball-json" / season / f"{code}.json"
    try:
        body = get_cached(url, cache)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            log.info("no football.json for %s %s", season, code)
            return []
        raise
    return _parse(json.loads(body), country)
