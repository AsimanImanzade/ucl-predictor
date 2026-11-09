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

SEASON = "2026-27"
PRESEASON_AS_OF = datetime(2026, 9, 7, tzinfo=UTC)
FINAL_VENUE_TEAM = "esp-atletico-madrid"
MODEL_NAME = "elo-dc-v1"
