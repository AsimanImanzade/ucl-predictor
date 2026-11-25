"""Fast refresh: re-fetch only the current CL season (optionally domestic) blocks.

One football-data request for the CL (teams come from the raw cache unless an unknown
team id appears). The block in matches.parquet is replaced only when something that
the export or the model reads has changed. Never runs the full ingest.
"""

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from uclpred.config import PROCESSED, RAW, SEASON, SEASONS, SNAPSHOTS
from uclpred.ingest.football_data import FD_COMPETITIONS, normalize_fd_match
from uclpred.ingest.run import write_processed_cl
from uclpred.matches import MATCH_COLUMNS, season_label, to_frame, validate_matches
from uclpred.snapshots import due_snapshots, store_ids

log = logging.getLogger(__name__)

YEAR = SEASONS[SEASON]["fd_year"]
DOMESTIC_FD = {code: comp for code, comp in FD_COMPETITIONS.items() if code != "CL"}
COMPARE = ["match_id", "date", "stage", "home_id", "away_id", "home_goals", "away_goals", "status", "neutral"]  # fmt: skip


@dataclass
class RefreshResult:
    changed: list[str] = field(default_factory=list)  # football-data codes
    due: list[tuple[str, datetime]] = field(default_factory=list)  # snapshots due

    @property
    def any(self) -> bool:
        return bool(self.changed or self.due)


def _rows(df: pd.DataFrame) -> list[tuple]:
    def py(v):
        if v is None or (not isinstance(v, (str, tuple)) and pd.isna(v)):
            return None
        if isinstance(v, pd.Timestamp):
            return v.tz_convert("UTC").isoformat()
        return v.item() if hasattr(v, "item") else v

    return sorted(tuple(py(v) for v in r) for r in df[COMPARE].itertuples(index=False))


def replace_block(
    df: pd.DataFrame, block: pd.DataFrame, comp: str, label: str
) -> tuple[pd.DataFrame, bool]:
    """Swap the (comp, label) rows for `block`. Returns (frame, changed); the input
    frame itself when nothing the model or export reads has changed."""
    if block.empty:
        raise ValueError(f"football-data {comp} {label} returned no matches; keeping the old block")
    mask = (df["competition"] == comp) & (df["season"] == label)
    if _rows(df[mask]) == _rows(block):
        return df, False
    out = pd.concat([df[~mask], block], ignore_index=True)
    out = out.sort_values(["date", "match_id"], kind="stable").reset_index(drop=True)[MATCH_COLUMNS]
    validate_matches(out)
    return out, True


def _latest_raw(raw_root: Path, code: str, year: int, kind: str) -> Path | None:
    cands = sorted(Path(raw_root).glob(f"*/{code}_{year}_{kind}.json"), key=lambda p: p.parent.name)
    return cands[-1] if cands else None


def refresh_competition(client, fd_code: str, year: int, df: pd.DataFrame, resolver, raw_root: Path):
    """Fetch one competition-season; returns (frame, changed, raw matches)."""
    matches = client.matches(fd_code, year)
    cached = _latest_raw(raw_root, fd_code, year, "teams")
    teams = json.loads(cached.read_text(encoding="utf-8"))["teams"] if cached else []
    ids = {t["id"]: t for t in teams}
    needed = {
        side["id"]
        for m in matches
        for side in (m["homeTeam"], m["awayTeam"])
        if side.get("id") is not None
    }
    if not needed <= ids.keys():
        teams = client.teams(fd_code, year)
    team_country = {t["id"]: t["area"]["code"] for t in teams}
    comp, label = FD_COMPETITIONS[fd_code], season_label(year)
    norm = (normalize_fd_match(m, team_country) for m in matches)
    rows = [(comp, label, m, "football-data") for m in norm if m is not None]
    out, changed = replace_block(df, to_frame(rows, resolver), comp, label)
    return out, changed, matches


def _write_parquet_atomic(df: pd.DataFrame, path: Path) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    try:
        df.to_parquet(tmp, index=False)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def run_refresh(
    client,
    domestic: bool = False,
    now: datetime | None = None,
    resolver=None,
    raw_root: Path = RAW / "football-data",
    processed_dir: Path = PROCESSED,
    store_dir: Path = SNAPSHOTS / SEASON,
) -> RefreshResult:
    """CL refresh; domestic blocks too when asked or when a snapshot is due (so an
    immutable snapshot never misses the domestic results before its as_of)."""
    from uclpred.teams import TeamResolver

    now = now or datetime.now(UTC)
    resolver = resolver or TeamResolver()
    matches_path = Path(processed_dir) / "matches.parquet"
    df = pd.read_parquet(matches_path)
    res = RefreshResult()

    df, changed, cl = refresh_competition(client, "CL", YEAR, df, resolver, raw_root)
    if changed:
        res.changed.append("CL")
    res.due = due_snapshots(cl, store_ids(store_dir), now)
    if domestic or res.due:
        for code in DOMESTIC_FD:
            df, ch, _ = refresh_competition(client, code, YEAR, df, resolver, raw_root)
            if ch:
                res.changed.append(code)
    if res.changed:
        # processed CL json first: a crash before the parquet write repeats the change
        write_processed_cl(years=(YEAR,), raw_root=raw_root, out_dir=processed_dir)
        _write_parquet_atomic(df, matches_path)
    return res


def write_github_output(changed: bool) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")
