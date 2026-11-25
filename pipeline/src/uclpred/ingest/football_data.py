"""football-data.org v4 client and match normaliser."""

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import requests

from uclpred.config import RAW
from uclpred.ingest.http_cache import atomic_write_bytes
from uclpred.ingest.openfootball_txt import RawMatch
from uclpred.teams import ISO3_TO_FIFA

BASE_URL = "https://api.football-data.org/v4"
MIN_INTERVAL_S = 6.5
MAX_429_RETRIES = 3
RESET_FALLBACK_S = 60.0
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


class FootballDataError(RuntimeError):
    """A football-data.org request failed. Never carries the request (it holds the token)."""


def _reset_seconds(headers) -> float:
    try:
        return max(float(headers.get("X-RequestCounter-Reset", RESET_FALLBACK_S)), 1.0)
    except (TypeError, ValueError):
        return RESET_FALLBACK_S


class FootballDataClient:
    """football-data.org v4 client with a per-day raw cache.

    force=True ignores today's cached file and overwrites it, so a run later the
    same day sees results that finished after the first fetch.
    """

    def __init__(self, token: str, force: bool = False):
        self._headers = {"X-Auth-Token": token}
        self._last_request_at: float | None = None
        self.force = force

    def _get_once(self, url: str):
        if self._last_request_at is not None:
            wait = MIN_INTERVAL_S - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
        try:
            return requests.get(url, headers=self._headers, timeout=30)
        except requests.RequestException as e:
            # `raise ... from None`: the original exception holds request.headers,
            # i.e. the token. Only its type name and the URL survive.
            raise FootballDataError(f"{type(e).__name__} fetching {url}") from None
        finally:
            self._last_request_at = time.monotonic()

    def _fetch(self, url: str) -> bytes:
        for attempt in range(MAX_429_RETRIES + 1):
            resp = self._get_once(url)
            if resp.status_code == 429 and attempt < MAX_429_RETRIES:
                time.sleep(_reset_seconds(resp.headers))
                continue
            break
        if resp.status_code == 403:
            raise PermissionError(f"football-data.org returned 403 for {url} (plan/permission)")
        if resp.status_code >= 400:
            raise FootballDataError(f"HTTP {resp.status_code} for {url}")
        # Minute quota used up: wait for the counter to reset before the next call.
        if resp.headers.get("X-Requests-Available-Minute") == "0":
            time.sleep(_reset_seconds(resp.headers))
        return resp.content

    def _get(self, path: str, code: str, season: int, kind: str) -> dict:
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        cache = RAW / "football-data" / day / f"{code}_{season}_{kind}.json"
        if cache.exists() and not self.force:
            return json.loads(cache.read_bytes())
        url = f"{BASE_URL}/competitions/{code}/{path}?season={season}"
        body = self._fetch(url)
        try:
            data = json.loads(body)
        except ValueError:
            raise FootballDataError(f"invalid JSON from {url}") from None
        if not isinstance(data, dict) or not isinstance(data.get(kind), list):
            raise FootballDataError(f"no '{kind}' list in response from {url}")
        atomic_write_bytes(cache, body)  # response body only; the token is a request header
        return data

    def matches(self, code: str, season: int) -> list[dict]:
        return self._get("matches", code, season, "matches")["matches"]

    def teams(self, code: str, season: int) -> list[dict]:
        return self._get("teams", code, season, "teams")["teams"]


def _pair(d: dict | None) -> tuple[int | None, int | None]:
    d = d or {}
    return d.get("home"), d.get("away")


def normalize_fd_match(m: dict, team_country: dict[int, str]) -> FdMatch | None:
    """Normalise one API match. team_country maps fd team id -> ISO3 area code.

    Returns None for an undetermined fixture (homeTeam or awayTeam id is null, as for
    knockout ties not yet drawn); callers skip those. A non-null team id that is missing
    from team_country raises KeyError.

    football-data's fullTime includes shoot-out goals for PENALTY_SHOOTOUT, so for any
    non-REGULAR duration the 90-minute score is regularTime and ET is regular + extra.
    """
    home, away = m["homeTeam"], m["awayTeam"]
    if home.get("id") is None or away.get("id") is None:
        return None
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
