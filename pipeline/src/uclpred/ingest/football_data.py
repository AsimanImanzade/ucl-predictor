"""football-data.org v4 client and match normaliser."""

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import requests

from uclpred.config import RAW
from uclpred.ingest.openfootball_txt import RawMatch
from uclpred.teams import ISO3_TO_FIFA

BASE_URL = "https://api.football-data.org/v4"
MIN_INTERVAL_S = 6.5
FD_COMPETITIONS = {
    "CL": "uefa.cl", "PL": "en.1", "PD": "es.1", "BL1": "de.1",
    "SA": "it.1", "FL1": "fr.1", "DED": "nl.1", "PPL": "pt.1",
}  # fmt: skip
PLAYED_STATUSES = {"FINISHED", "AWARDED"}


@dataclass
class FdMatch(RawMatch):
    fd_id: int
    matchday: int | None
    status: str
    home_fd_id: int
    away_fd_id: int
    home_tla: str
    away_tla: str
    home_crest: str
    away_crest: str


class FootballDataClient:
    def __init__(self, token: str):
        self._headers = {"X-Auth-Token": token}
        self._last_request_at: float | None = None

    def _fetch(self, url: str) -> bytes:
        if self._last_request_at is not None:
            wait = MIN_INTERVAL_S - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
        try:
            resp = requests.get(url, headers=self._headers, timeout=30)
        finally:
            self._last_request_at = time.monotonic()
        if resp.status_code == 403:
            raise PermissionError(f"football-data.org returned 403 for {url} (plan/permission)")
        resp.raise_for_status()
        # Out of quota: wait for the counter to reset before the next call.
        h = resp.headers
        if h.get("X-Requests-Available") == "0":
            time.sleep(float(h.get("X-RequestCounter-Reset", MIN_INTERVAL_S)))
        return resp.content

    def _get(self, path: str, code: str, season: int, kind: str) -> dict:
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        cache = RAW / "football-data" / day / f"{code}_{season}_{kind}.json"
        if cache.exists():
            return json.loads(cache.read_bytes())
        body = self._fetch(f"{BASE_URL}/competitions/{code}/{path}?season={season}")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(body)  # response body only; the token is a request header
        return json.loads(body)

    def matches(self, code: str, season: int) -> list[dict]:
        return self._get("matches", code, season, "matches")["matches"]

    def teams(self, code: str, season: int) -> list[dict]:
        return self._get("teams", code, season, "teams")["teams"]


def _pair(d: dict | None) -> tuple[int | None, int | None]:
    d = d or {}
    return d.get("home"), d.get("away")


def normalize_fd_match(m: dict, team_country: dict[int, str]) -> FdMatch:
    """Normalise one API match. team_country maps fd team id -> ISO3 area code.

    football-data's fullTime includes shoot-out goals for PENALTY_SHOOTOUT, so for any
    non-REGULAR duration the 90-minute score is regularTime and ET is regular + extra.
    """
    score = m.get("score") or {}
    duration = score.get("duration", "REGULAR")
    if duration == "REGULAR":
        hg, ag = _pair(score.get("fullTime"))
        eh = ea = ph = pa = None
    else:
        hg, ag = _pair(score.get("regularTime"))
        xh, xa = _pair(score.get("extraTime"))
        if hg is None or ag is None:
            eh = ea = None
        else:
            eh, ea = hg + (xh or 0), ag + (xa or 0)
        ph, pa = _pair(score.get("penalties"))
    home, away = m["homeTeam"], m["awayTeam"]

    def country(tid: int) -> str:
        iso = team_country[tid]
        return ISO3_TO_FIFA.get(iso, iso)

    stage = m.get("stage") or ""
    return FdMatch(
        date=datetime.fromisoformat(m["utcDate"]),
        stage=stage,
        home_name=home["name"],
        home_country=country(home["id"]),
        away_name=away["name"],
        away_country=country(away["id"]),
        home_goals=hg,
        away_goals=ag,
        et_home=eh,
        et_away=ea,
        pens_home=ph,
        pens_away=pa,
        neutral=stage == "FINAL",
        fd_id=m["id"],
        matchday=m.get("matchday"),
        status=m["status"],
        home_fd_id=home["id"],
        away_fd_id=away["id"],
        home_tla=home.get("tla") or "",
        away_tla=away.get("tla") or "",
        home_crest=home.get("crest") or "",
        away_crest=away.get("crest") or "",
    )
