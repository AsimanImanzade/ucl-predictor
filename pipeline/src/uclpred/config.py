"""Project-wide paths and constants."""

from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
REFERENCE = DATA / "reference"
EXPORT = DATA / "export"
REPORTS = ROOT / "reports"

SEASONS: dict[str, dict] = {
    "2024-25": {
        "fd_year": 2024,
        "preseason_as_of": datetime(2024, 9, 16, tzinfo=UTC),
        "final_venue_team": "ger-bayern-munchen",
    },
    "2025-26": {
        "fd_year": 2025,
        "preseason_as_of": datetime(2025, 9, 15, tzinfo=UTC),
        "final_venue_team": None,
    },
    "2026-27": {
        "fd_year": 2026,
        "preseason_as_of": datetime(2026, 9, 7, tzinfo=UTC),
        "final_venue_team": "esp-atletico-madrid",
    },
}
SEASON = "2026-27"
PRESEASON_AS_OF = SEASONS[SEASON]["preseason_as_of"]
FINAL_VENUE_TEAM = SEASONS[SEASON]["final_venue_team"]
MODEL_NAME = "elo-dc-v1"
