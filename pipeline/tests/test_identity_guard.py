from datetime import UTC, datetime

import pandas as pd

from uclpred import identity_guard as ig
from uclpred.identity_guard import euro_without_domestic, thin_history
from uclpred.teams import TeamResolver


def _row(i, date, season, comp, h, a):
    return {
        "match_id": f"m{i}",
        "date": pd.Timestamp(date, tz="UTC"),
        "season": season,
        "competition": comp,
        "home_id": h,
        "away_id": a,
        "home_goals": 1,
        "away_goals": 0,
        "neutral": False,
        "status": "FINISHED",
    }


def _frame(rows):
    return pd.DataFrame([_row(i, *r) for i, r in enumerate(rows)])


def test_euro_only_club_before_domestic_data_not_flagged():
    m = _frame([("2015-10-01", "2015-16", "uefa.el", "ned-euroonly", "eng-x")])
    assert euro_without_domestic(m) == []


def test_euro_only_club_in_season_with_domestic_data_flagged():
    m = _frame(
        [
            ("2019-10-01", "2019-20", "uefa.el", "ned-euroonly", "eng-x"),
            ("2019-10-05", "2019-20", "nl.1", "ned-a", "ned-b"),
            ("2019-10-06", "2019-20", "en.1", "eng-x", "eng-y"),
        ]
    )
    assert euro_without_domestic(m) == [("ned-euroonly", "2019-20")]


def test_club_with_domestic_match_and_unmapped_country_not_flagged():
    m = _frame(
        [
            ("2019-10-01", "2019-20", "uefa.cl", "ned-a", "aze-sabah"),
            ("2019-10-05", "2019-20", "nl.1", "ned-a", "ned-b"),
        ]
    )
    assert euro_without_domestic(m) == []


def test_thin_history():
    rows = [
        (f"2024-01-{d + 1:02d}", "2023-24", "nl.1", "ned-thin", "ned-x")
        for d in range(5)
    ]
    rows += [
        (f"2024-02-{d + 1:02d}", "2023-24", "nl.1", "ned-thick", "ned-x")
        for d in range(25)
    ]
    rows.append(("2024-06-01", "2023-24", "nl.1", "ned-thin", "ned-x"))  # after as_of
    m = _frame(rows)
    as_of = datetime(2024, 5, 1, tzinfo=UTC)
    assert thin_history(["ned-thin", "ned-thick"], m, as_of) == ["ned-thin"]


def test_exceptions_loaded_and_excluded(tmp_path, monkeypatch):
    p = tmp_path / "exc.csv"
    p.write_text("team_id,reason\nned-euroonly,newcomer\n")
    monkeypatch.setattr(ig, "EXCEPTIONS_PATH", p)
    assert ig.load_exceptions() == {"ned-euroonly"}
    m = _frame(
        [
            ("2019-10-01", "2019-20", "uefa.el", "ned-euroonly", "eng-x"),
            ("2019-10-05", "2019-20", "nl.1", "ned-a", "ned-b"),
        ]
    )
    assert euro_without_domestic(m) == [("ned-euroonly", "2019-20")]
    assert euro_without_domestic(m, exceptions=ig.load_exceptions()) == []


def test_real_aliases_unify_identities():
    r = TeamResolver()
    for n in ["FC Red Bull Salzburg", "Red Bull Salzburg", "Salzburg"]:
        assert r.resolve("AUT", n) == "aut-rb-salzburg"
    assert r.resolve("ITA", "SS Lazio") == "ita-lazio-roma"
    assert r.resolve("POR", "Vitória") == "por-vitoria-guimaraes"
