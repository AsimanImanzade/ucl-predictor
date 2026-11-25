"""Matchday snapshots: when a matchday is complete and which snapshots are due."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from uclpred.snapshots import (
    complete_matchdays,
    due_snapshots,
    snapshot_as_of,
    store_ids,
)

ROOT = Path(__file__).resolve().parents[2]


def _league(played_through=4, half=None):
    """8 matchdays x 18; MD n kicks off on day 7n (two evenings). `half` = MD half-played."""
    base = datetime(2026, 9, 8, 17, 45, tzinfo=UTC)
    out = []
    for md in range(1, 9):
        for j in range(18):
            ko = base + timedelta(days=7 * (md - 1) + j % 2, hours=2 * (j % 3 == 0))
            done = md <= played_through or (md == half and j % 2 == 0)
            out.append({
                "id": md * 100 + j, "matchday": md, "stage": "LEAGUE_STAGE",
                "utcDate": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "FINISHED" if done else "TIMED",
            })  # fmt: skip
    out.append({"id": 1, "matchday": None, "stage": "PLAYOFFS", "utcDate": "2027-02-16T20:00:00Z", "status": "TIMED"})
    return out


def test_complete_matchdays_needs_all_18():
    assert complete_matchdays(_league(4, half=5)) == [1, 2, 3, 4]
    ms = _league(4)
    ms[0]["status"] = "AWARDED"
    assert complete_matchdays(ms) == [1, 2, 3, 4]
    ms[1]["status"] = "POSTPONED"
    assert complete_matchdays(ms) == [2, 3, 4]


def test_as_of_is_day_after_last_kickoff():
    # MD1: kickoffs on 8 and 9 Sep, the latest at 19:45 on the 9th -> 10 Sep 00:00
    assert snapshot_as_of(_league(), 1) == datetime(2026, 9, 10, tzinfo=UTC)


def test_due_only_missing_and_after_as_of():
    ms = _league(5)
    as_of5 = snapshot_as_of(ms, 5)
    have = {"md00", "md01", "md02", "md03", "md04"}
    assert due_snapshots(ms, have, as_of5 - timedelta(minutes=1)) == []
    assert due_snapshots(ms, have, as_of5) == [("md05", as_of5)]
    assert due_snapshots(ms, have | {"md05"}, as_of5) == []
    assert [s for s, _ in due_snapshots(ms, {"md00"}, as_of5)] == ["md01", "md02", "md03", "md04", "md05"]


def test_store_ids(tmp_path):
    for n in ("md00.json", "md01.json", "live.json", "notes.txt"):
        (tmp_path / n).write_text("{}")
    assert store_ids(tmp_path) == {"md00", "md01"}
    assert store_ids(tmp_path / "missing") == set()


@pytest.mark.data
def test_real_as_of_matches_published_snapshots():
    fd = json.loads((ROOT / "data/processed/cl_2026_fd.json").read_text())
    manifest = json.loads((ROOT / "web/public/data/manifest.json").read_text())
    published = {s["id"]: s["asOf"] for s in manifest["snapshots"] if s["id"].startswith("md") and s["id"] != "md00"}
    for sid, as_of in published.items():
        assert snapshot_as_of(fd, int(sid[2:])).strftime("%Y-%m-%dT%H:%M:%SZ") == as_of


def test_postponed_match_blocks_later_snapshots():
    ms = _league(6)
    postponed = next(m for m in ms if m["matchday"] == 5)
    postponed["status"] = "POSTPONED"  # MD5 open, MD6 complete
    now = snapshot_as_of(ms, 6)
    assert complete_matchdays(ms) == [1, 2, 3, 4, 6]
    assert due_snapshots(ms, {"md00", "md01", "md02", "md03", "md04"}, now) == []
    postponed["status"] = "FINISHED"
    assert [s for s, _ in due_snapshots(ms, {"md00", "md01", "md02", "md03", "md04"}, now)] == ["md05", "md06"]
