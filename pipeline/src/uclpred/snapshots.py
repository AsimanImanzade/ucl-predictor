"""Immutable matchday snapshots: completeness, as_of and which ones are due."""

from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

from uclpred.ingest.football_data import PLAYED_STATUSES

MATCHES_PER_MATCHDAY = 18


def _league_by_matchday(fd_matches: list[dict]) -> dict[int, list[dict]]:
    by_md: dict[int, list[dict]] = defaultdict(list)
    for m in fd_matches:
        if m.get("stage") == "LEAGUE_STAGE" and m.get("matchday"):
            by_md[int(m["matchday"])].append(m)
    return by_md


def complete_matchdays(fd_matches: list[dict]) -> list[int]:
    """League-phase matchdays whose 18 fixtures are all played."""
    return sorted(
        md
        for md, ms in _league_by_matchday(fd_matches).items()
        if len(ms) == MATCHES_PER_MATCHDAY and all(m["status"] in PLAYED_STATUSES for m in ms)
    )


def snapshot_as_of(fd_matches: list[dict], matchday: int) -> datetime:
    """Midnight UTC after the matchday's last kickoff (the md01..md04 convention)."""
    last = max(
        datetime.fromisoformat(m["utcDate"]).astimezone(UTC)
        for m in _league_by_matchday(fd_matches)[matchday]
    )
    return datetime.combine(last.date() + timedelta(days=1), time(0), tzinfo=UTC)


def store_ids(store_dir: Path) -> set[str]:
    """Snapshot ids already in the immutable store (data/snapshots/<season>/mdNN.json)."""
    return {p.stem for p in Path(store_dir).glob("md*.json")}


def due_snapshots(
    fd_matches: list[dict], existing: set[str], now: datetime
) -> list[tuple[str, datetime]]:
    """(id, as_of) for complete matchdays without a stored snapshot whose as_of has passed.

    Waiting for as_of keeps every snapshot's as_of <= the live export's. Only the
    unbroken run 1..N of complete matchdays counts: "after matchday N" needs every
    earlier matchday played too (build-data checks the same), so a match postponed
    past the next matchday holds the later snapshots back instead of failing.
    """
    out = []
    complete = set(complete_matchdays(fd_matches))
    md = 1
    while md in complete:
        sid, as_of = f"md{md:02d}", snapshot_as_of(fd_matches, md)
        md += 1
        if sid not in existing and as_of <= now:
            out.append((sid, as_of))
    return out
