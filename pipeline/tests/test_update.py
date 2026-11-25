"""`uclpred update`: exports, sims and build-data in the right order, no network."""

import json
from datetime import UTC, datetime

from test_snapshots import _league

from uclpred.snapshots import snapshot_as_of
from uclpred.update import run_update, sim_command


def _setup(tmp_path, fd):
    proc, store = tmp_path / "processed", tmp_path / "store"
    proc.mkdir()
    store.mkdir()
    (proc / "cl_2026_fd.json").write_text(json.dumps(fd))
    for sid in ("md00", "md01", "md02", "md03", "md04"):
        (store / f"{sid}.json").write_text("{}")
    return proc, store


def _go(tmp_path, fd, now):
    proc, store = _setup(tmp_path, fd)
    exports, cmds = [], []
    ids = run_update(
        now=now, runner=cmds.append, export=lambda a, out: exports.append((a, out.name)) or "ok",
        processed_dir=proc, store_dir=store, export_dir=tmp_path / "export",
    )  # fmt: skip
    return ids, exports, cmds


def test_live_only_mid_matchday(tmp_path):
    now = datetime(2026, 11, 25, 7, 3, 9, 123, tzinfo=UTC)
    ids, exports, cmds = _go(tmp_path, _league(4, half=5), now)
    assert ids == ["live"]
    assert exports == [(now.replace(microsecond=0), "live")]
    assert cmds == [sim_command("live"), [cmds[-1][0], "--filter", "@uclpred/web", "build-data", "live"]]


def test_completed_matchday_builds_snapshot_first(tmp_path):
    fd = _league(5)
    as_of5 = snapshot_as_of(fd, 5)
    ids, exports, cmds = _go(tmp_path, fd, as_of5.replace(hour=6))
    assert ids == ["md05", "live"]
    assert exports[0] == (as_of5, "md05") and exports[1][1] == "live"
    assert cmds[-1][-2:] == ["md05", "live"]


def test_sim_command_is_official_run():
    cmd = sim_command("live")
    assert cmd[cmd.index("--runs") + 1] == "50000"
    assert cmd[cmd.index("--seed") + 1] == "1"
    assert cmd[cmd.index("--sigma") + 1] == "0"
    assert cmd[cmd.index("--input") + 1] == "data/export/live"
