"""`uclpred update`: rebuild the site data from data/processed (no network).

Exports `live` (as_of = now) and every due `mdNN` snapshot, runs the official
simulation for each (50,000 runs, seed 1, sigma 0) and assembles web/public/data
with build-data, which also writes new snapshots to the immutable store.
"""

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from uclpred.config import EXPORT, PROCESSED, ROOT, SEASON, SEASONS, SNAPSHOTS
from uclpred.snapshots import due_snapshots, store_ids

RUNS, SEED, SIGMA = 50_000, 1, 0


def _pnpm() -> str:
    return os.environ.get("PNPM", "pnpm")


def sim_command(sid: str) -> list[str]:
    return [
        _pnpm(), "--filter", "@uclpred/sim", "cli", "--",
        "--input", f"data/export/{sid}",
        "--runs", str(RUNS), "--seed", str(SEED), "--sigma", str(SIGMA),
    ]  # fmt: skip


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def run_update(
    now: datetime | None = None,
    runner=_run,
    export=None,
    processed_dir: Path = PROCESSED,
    store_dir: Path = SNAPSHOTS / SEASON,
    export_dir: Path = EXPORT,
) -> list[str]:
    """Returns the snapshot ids built from data/export (new mdNN first, then live)."""
    if export is None:
        from uclpred.export import run_export as export
    now = (now or datetime.now(UTC)).replace(microsecond=0)
    fd_year = SEASONS[SEASON]["fd_year"]
    fd = json.loads((Path(processed_dir) / f"cl_{fd_year}_fd.json").read_text(encoding="utf-8"))
    due = due_snapshots(fd, store_ids(store_dir), now)
    ids = [sid for sid, _ in due] + ["live"]
    for sid, as_of in [*due, ("live", now)]:
        print(export(as_of, Path(export_dir) / sid))
    for sid in ids:
        runner(sim_command(sid))
    runner([_pnpm(), "--filter", "@uclpred/web", "build-data", *ids])
    return ids
