"""Canonical match table: build, combine across sources, validate, load."""

import pandas as pd

from uclpred.config import PROCESSED
from uclpred.ingest.football_data import PLAYED_STATUSES, FdMatch
from uclpred.ingest.openfootball_txt import RawMatch
from uclpred.teams import TeamResolver

MATCH_COLUMNS = [
    "match_id", "date", "season", "competition", "stage", "home_id", "away_id",
    "home_goals", "away_goals", "neutral", "status", "source",
]  # fmt: skip
SOURCE_PRIORITY = {"football-data": 0, "openfootball": 1}
MATCHES_PATH = PROCESSED / "matches.parquet"


def season_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def to_frame(
    rows: list[tuple[str, str, RawMatch | FdMatch, str]], resolver: TeamResolver
) -> pd.DataFrame:
    """rows are (competition, season, match, source)."""
    recs = []
    for comp, season, m, source in rows:
        home = resolver.resolve(m.home_country, m.home_name)
        away = resolver.resolve(m.away_country, m.away_name)
        if isinstance(m, FdMatch):
            finished = m.status in PLAYED_STATUSES
            mid = f"fd:{m.fd_id}"
        else:
            finished = m.home_goals is not None and m.away_goals is not None
            mid = f"of:{comp}:{m.date:%Y-%m-%d}:{home}:{away}"
        recs.append({
            "match_id": mid, "date": m.date, "season": season, "competition": comp,
            "stage": m.stage, "home_id": home, "away_id": away,
            "home_goals": m.home_goals if finished else None,
            "away_goals": m.away_goals if finished else None,
            "neutral": bool(m.neutral),
            "status": "FINISHED" if finished else "SCHEDULED",
            "source": source,
        })  # fmt: skip
    df = pd.DataFrame(recs, columns=MATCH_COLUMNS)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    for c in ("home_goals", "away_goals"):
        df[c] = df[c].astype("Int64")
    df["neutral"] = df["neutral"].astype(bool)
    return df


def combine(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Per (competition, season) keep only the highest-priority source; sort by date."""
    df = pd.concat([f for f in frames if len(f)], ignore_index=True)
    rank = df["source"].map(SOURCE_PRIORITY)
    best = rank.groupby([df["competition"], df["season"]]).transform("min")
    df = df[rank == best]
    return df.sort_values(["date", "match_id"], kind="stable").reset_index(drop=True)[
        MATCH_COLUMNS
    ]


def validate_matches(df: pd.DataFrame) -> None:
    problems = []
    dup = df[df.duplicated(["date", "home_id", "away_id"], keep=False)]
    for _, r in dup.drop_duplicates(["date", "home_id", "away_id"]).iterrows():
        problems.append(
            f"duplicate match {r.date} {r.home_id} v {r.away_id} ({r.competition} {r.season})"
        )
    if df["match_id"].duplicated().any():
        ids = sorted(df.loc[df["match_id"].duplicated(), "match_id"].unique())
        problems.append(f"duplicate match_id: {ids[:10]}")
    for _, r in df[(df.home_goals < 0) | (df.away_goals < 0)].iterrows():
        problems.append(f"negative goals {r.match_id}")
    fin = df[(df.status == "FINISHED") & (df.home_goals.isna() | df.away_goals.isna())]
    for _, r in fin.iterrows():
        problems.append(f"FINISHED without goals {r.match_id}")
    for _, r in df[df.home_id == df.away_id].iterrows():
        problems.append(f"team plays itself {r.match_id} ({r.home_id})")
    if problems:
        raise ValueError(f"{len(problems)} match problems:\n" + "\n".join(problems))


def load_matches() -> pd.DataFrame:
    return pd.read_parquet(MATCHES_PATH)
