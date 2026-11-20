import json

import pytest

from uclpred.config import PRESEASON_AS_OF, PROCESSED
from uclpred.elo import run_elo
from uclpred.matches import load_matches
from uclpred.teams import DEFAULT_ALIASES_PATH, TeamResolver

BIG = {
    "esp-real-madrid", "ger-bayern-munchen", "fra-paris-saint-germain",
    "ita-internazionale-milano", "eng-arsenal", "eng-liverpool",
    "eng-manchester-city", "esp-barcelona",
}  # fmt: skip


@pytest.mark.data
def test_preseason_top10_contains_big_clubs():
    res = run_elo(load_matches())
    teams = json.loads((PROCESSED / "cl_2026_teams.json").read_text())
    resolver = TeamResolver(DEFAULT_ALIASES_PATH)
    ids = [resolver.resolve(t["area"]["code"], t["name"]) for t in teams]
    assert len(ids) == 36
    ratings = res.ratings_as_of(PRESEASON_AS_OF)
    ranked = sorted(((ratings[i], i) for i in ids), reverse=True)
    for r, i in ranked[:10]:
        print(f"{i:35s} {r:7.1f}")
    assert len({i for _, i in ranked[:10]} & BIG) >= 6
