"""UEFA club coefficients from the comp.uefa.com v2 endpoint (fetched once, cached)."""

import json

import pandas as pd

from uclpred.config import RAW, REFERENCE
from uclpred.ingest.http_cache import get_cached
from uclpred.teams import TeamResolver

COEF_URL = (
    "https://comp.uefa.com/v2/coefficients?coefficientRange=OVERALL"
    "&coefficientType=MEN_CLUB&language=EN&page=1&pagesize=500&seasonYear={season_year}"
)
COEF_COLUMNS = ["season_year", "team_id", "name", "country", "total_5y"]
COEF_PATH = REFERENCE / "coefficients.csv"
_HEADERS = {"User-Agent": "Mozilla/5.0 (uclpred)"}


def parse_coefficients(
    payload: dict, season_year: int, resolver: TeamResolver
) -> pd.DataFrame:
    """Map the endpoint JSON to COEF_COLUMNS.

    members[].member.{internationalName, countryCode (FIFA style)} and
    members[].overallRanking.totalValue (5-year coefficient points).
    """
    rows = []
    for item in payload["data"]["members"]:
        mem = item["member"]
        if mem.get("isPlaceHolder"):
            continue
        name = mem.get("internationalName") or mem["displayName"]
        country = mem["countryCode"]
        rows.append({
            "season_year": season_year,
            "team_id": resolver.resolve(country, name),
            "name": name,
            "country": country,
            "total_5y": float(item["overallRanking"]["totalValue"]),
        })  # fmt: skip
    return pd.DataFrame(rows, columns=COEF_COLUMNS)


def fetch_coefficients(
    season_year: int, resolver: TeamResolver | None = None
) -> pd.DataFrame:
    resolver = resolver or TeamResolver()
    raw = get_cached(
        COEF_URL.format(season_year=season_year),
        RAW / "uefa" / f"coef_{season_year}.json",
        headers=_HEADERS,
    )
    return parse_coefficients(json.loads(raw), season_year, resolver)


def save_coefficients(df: pd.DataFrame, path=COEF_PATH) -> pd.DataFrame:
    """Replace rows for the fetched season year(s), keep the others."""
    dup = df[df.duplicated(["season_year", "team_id"], keep=False)]
    if len(dup):
        raise ValueError(
            "duplicate team_id within season_year (alias collision?): "
            + ", ".join(sorted(set(dup["team_id"])))
        )
    if path.exists():
        old = pd.read_csv(path)
        old = old[~old["season_year"].isin(df["season_year"].unique())]
        df = pd.concat([old, df], ignore_index=True)
    df = df.sort_values(["season_year", "team_id"]).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df
