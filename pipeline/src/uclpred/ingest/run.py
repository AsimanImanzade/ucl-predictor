"""Network orchestration for `uclpred ingest`."""

import json
import logging

from uclpred.config import PROCESSED
from uclpred.ingest.football_data import (
    FD_COMPETITIONS,
    FootballDataClient,
    normalize_fd_match,
)
from uclpred.ingest.openfootball_json import DOMESTIC_CODES, load_football_json
from uclpred.ingest.openfootball_txt import load_openfootball_euro
from uclpred.matches import (
    MATCHES_PATH,
    combine,
    season_label,
    to_frame,
    validate_matches,
)
from uclpred.teams import TeamResolver

log = logging.getLogger(__name__)

EURO_SEASONS = [season_label(y) for y in range(2011, 2026)]  # 2011-12 .. 2025-26
JSON_SEASONS = [season_label(y) for y in range(2010, 2027)]  # 2010-11 .. 2026-27
FD_SEASONS = {"CL": [2024, 2025, 2026]}
FD_SEASONS.update({c: [2025, 2026] for c in FD_COMPETITIONS if c != "CL"})


def run_ingest(token: str) -> None:
    resolver = TeamResolver()
    frames = []

    for season in EURO_SEASONS:
        rows = [
            (code, season, m, "openfootball")
            for code, m in load_openfootball_euro(season)
        ]
        frames.append(to_frame(rows, resolver))
    for season in JSON_SEASONS:
        for code in DOMESTIC_CODES:
            rows = [
                (code, season, m, "openfootball")
                for m in load_football_json(season, code)
            ]
            frames.append(to_frame(rows, resolver))

    client = FootballDataClient(token)
    for fd_code, seasons in FD_SEASONS.items():
        comp = FD_COMPETITIONS[fd_code]
        for year in seasons:
            label = season_label(year)
            try:
                teams = client.teams(fd_code, year)
                matches = client.matches(fd_code, year)
            except PermissionError as e:
                log.warning("skipping football-data %s %s: %s", fd_code, label, e)
                print(f"skipped football-data {fd_code} {label} (403)")
                continue
            team_country = {t["id"]: t["area"]["code"] for t in teams}
            norm = (normalize_fd_match(m, team_country) for m in matches)
            rows = [(comp, label, m, "football-data") for m in norm if m is not None]
            frames.append(to_frame(rows, resolver))
            if fd_code == "CL" and year == 2026:
                PROCESSED.mkdir(parents=True, exist_ok=True)
                (PROCESSED / "cl_2026_fd.json").write_text(
                    json.dumps(matches), encoding="utf-8"
                )
                (PROCESSED / "cl_2026_teams.json").write_text(
                    json.dumps(teams), encoding="utf-8"
                )

    df = combine(frames)
    validate_matches(df)
    MATCHES_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(MATCHES_PATH, index=False)
    counts = df.groupby(["competition", "season"]).agg(
        rows=("match_id", "size"),
        finished=("status", lambda s: int((s == "FINISHED").sum())),
    )
    print(counts.to_string())
    print(f"total rows: {len(df)} -> {MATCHES_PATH}")
