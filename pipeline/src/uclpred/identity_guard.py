"""Data guards against club-identity splits (same club under two team ids)."""

import csv
from datetime import datetime

import pandas as pd

from uclpred.config import REFERENCE
from uclpred.teams import LEAGUE_COUNTRY

EXCEPTIONS_PATH = REFERENCE / "identity_exceptions.csv"

_TOP_DIVISION = {country: f"{code}.1" for code, country in LEAGUE_COUNTRY.items()}


def load_exceptions() -> set[str]:
    """Reviewed allow-list of team ids (genuine newcomers / Euro-only clubs)."""
    with open(EXCEPTIONS_PATH, newline="", encoding="utf-8-sig") as f:
        return {
            row["team_id"].strip()
            for row in csv.DictReader(f)
            if row["team_id"].strip()
        }


def euro_without_domestic(
    matches: pd.DataFrame, exceptions: set[str] | None = None
) -> list[tuple[str, str]]:
    """(team_id, season) pairs where a club plays in Europe but not at home.

    Only seasons in which the club's country top division is present in the
    data are checked, so genuine Euro-only clubs of earlier years are not flagged.
    """
    finished = matches[matches["status"] == "FINISHED"]
    sides = pd.concat(
        [
            finished[["season", "competition", "home_id"]].rename(
                columns={"home_id": "team_id"}
            ),
            finished[["season", "competition", "away_id"]].rename(
                columns={"away_id": "team_id"}
            ),
        ]
    )
    euro = sides[sides["competition"].str.startswith("uefa.")]
    domestic = sides[~sides["competition"].str.startswith("uefa.")]
    domestic_pairs = set(zip(domestic["team_id"], domestic["season"], strict=True))
    top_present = set(zip(finished["season"], finished["competition"], strict=True))
    skip = exceptions or set()
    out: set[tuple[str, str]] = set()
    for team_id, season in set(zip(euro["team_id"], euro["season"], strict=True)):
        if team_id in skip:
            continue
        top = _TOP_DIVISION.get(team_id.split("-", 1)[0].upper())
        if top is None or (season, top) not in top_present:
            continue
        if (team_id, season) not in domestic_pairs:
            out.add((team_id, season))
    return sorted(out)


def thin_history(
    team_ids: list[str],
    matches: pd.DataFrame,
    as_of: datetime,
    min_matches: int = 20,
) -> list[str]:
    """Team ids with fewer than min_matches FINISHED matches before as_of."""
    prior = matches[(matches["status"] == "FINISHED") & (matches["date"] < as_of)]
    counts = pd.concat([prior["home_id"], prior["away_id"]]).value_counts()
    return sorted(t for t in team_ids if counts.get(t, 0) < min_matches)
