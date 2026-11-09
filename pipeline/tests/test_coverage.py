from datetime import UTC, datetime

import pandas as pd

from uclpred.coverage import coverage_report, duplicate_candidates


def mk(rows):
    recs = [
        {"match_id": f"m{i}", "date": datetime(2025, 9, 1 + i, tzinfo=UTC),
         "season": "2025-26", "competition": comp, "home_id": h, "away_id": a,
         "source": src}
        for i, (h, a, comp, src) in enumerate(rows)
    ]  # fmt: skip
    return pd.DataFrame(recs)


def test_duplicate_candidates_found():
    df = mk([
        ("por-benfica", "por-porto", "pt.1", "openfootball"),
        ("por-sport-lisboa-e-benfica", "por-sporting", "pt.1", "openfootball"),
    ])  # fmt: skip
    assert ("por-benfica", "por-sport-lisboa-e-benfica") in duplicate_candidates(df)


def test_duplicate_candidates_skips_pairs_that_met():
    df = mk([("por-benfica", "por-sport-lisboa-e-benfica", "pt.1", "openfootball")])
    assert duplicate_candidates(df) == []


def test_duplicate_candidates_other_country_ignored():
    df = mk([
        ("por-benfica", "por-porto", "pt.1", "openfootball"),
        ("esp-sport-lisboa-e-benfica", "esp-x", "es.1", "openfootball"),
    ])  # fmt: skip
    assert duplicate_candidates(df) == []


def test_coverage_report_zero_matches_no_crash():
    df = mk([("eng-arsenal", "eng-chelsea", "en.1", "football-data")])
    teams = [{"name": "Ghost FC", "area": {"code": "ENG"}}]
    coefs = pd.DataFrame(
        columns=["season_year", "team_id", "name", "country", "total_5y"]
    )
    out = coverage_report(df, teams, coefs)
    assert "eng-ghost" in out
    assert "| 0 |" in out
    assert "missing" in out
