import json

import pytest

from uclpred.config import DATA, SEASONS
from uclpred.identity_guard import euro_without_domestic, load_exceptions, thin_history
from uclpred.matches import load_matches
from uclpred.teams import TeamResolver


def _export_team_ids(season: str) -> list[str]:
    paths = sorted((DATA / "export" / "bt" / season).glob("*/season.json"))
    if not paths:  # current season lives in md00
        paths = [DATA / "export" / "md00" / "season.json"]
    # Past-season exports were written before the alias fixes; re-resolve each
    # team through the current resolver so stale ids map to today's canonical id.
    resolver = TeamResolver()
    ids: set[str] = set()
    for p in paths:
        for t in json.loads(p.read_text())["teams"]:
            ids.add(resolver.resolve(t["country"], t["name"]))
    return sorted(ids)


@pytest.mark.data
def test_no_euro_without_domestic_split():
    flagged = euro_without_domestic(load_matches(), exceptions=load_exceptions())
    print(f"\neuro_without_domestic (minus exceptions): {flagged}")
    assert flagged == []


@pytest.mark.data
def test_no_thin_history_at_preseason():
    matches = load_matches()
    exc = load_exceptions()
    for season, cfg in SEASONS.items():
        ids = [t for t in _export_team_ids(season) if t not in exc]
        thin = thin_history(ids, matches, cfg["preseason_as_of"])
        print(f"\n{season}: {len(ids)} teams, thin_history={thin}")
        assert thin == [], season
