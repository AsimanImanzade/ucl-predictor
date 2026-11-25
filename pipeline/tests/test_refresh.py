"""Fast CL refresh: replace one competition-season block, detect real changes only."""

import json
from datetime import UTC, datetime

import pandas as pd
import pytest

from uclpred import refresh
from uclpred.matches import to_frame
from uclpred.refresh import (
    refresh_competition,
    replace_block,
    run_refresh,
    write_github_output,
)

LABEL = "2026-27"


class Resolver:
    def resolve(self, country, name):
        return f"{country.lower()}-{name.lower()}"


def _m(mid, status="FINISHED", hg=1, ag=0, home=1, away=2, md=1, date="2026-11-24T20:00:00Z"):
    return {
        "id": mid, "utcDate": date, "status": status, "matchday": md, "stage": "LEAGUE_STAGE",
        "homeTeam": {"id": home, "name": f"T{home}"}, "awayTeam": {"id": away, "name": f"T{away}"},
        "score": {"duration": "REGULAR", "fullTime": {"home": hg, "away": ag}},
    }  # fmt: skip


TEAMS = [{"id": i, "name": f"T{i}", "area": {"code": "ENG"}} for i in range(1, 7)]


class Client:
    def __init__(self, matches, teams=TEAMS):
        self._matches, self._teams, self.calls = matches, teams, []

    def matches(self, code, year):
        self.calls.append(("matches", code, year))
        return self._matches.get(code, []) if isinstance(self._matches, dict) else self._matches

    def teams(self, code, year):
        self.calls.append(("teams", code, year))
        return self._teams


def _frame(matches, comp="uefa.cl"):
    from uclpred.ingest.football_data import normalize_fd_match

    tc = {t["id"]: t["area"]["code"] for t in TEAMS}
    rows = [(comp, LABEL, normalize_fd_match(m, tc), "football-data") for m in matches]
    return to_frame(rows, Resolver())


def _base():
    other = _frame([_m(900, home=5, away=6, date="2026-11-22T15:00:00Z")], comp="en.1")
    cl = _frame([_m(1), _m(2, status="TIMED", home=3, away=4, date="2026-11-25T20:00:00Z")])
    return pd.concat([other, cl], ignore_index=True)


def test_replace_block_updates_scores_only_in_that_block():
    df = _base()
    new = _frame([_m(1), _m(2, hg=2, ag=2, home=3, away=4, date="2026-11-25T20:00:00Z")])
    out, changed = replace_block(df, new, "uefa.cl", LABEL)
    assert changed
    row = out[out.match_id == "fd:2"].iloc[0]
    assert (row.home_goals, row.away_goals, row.status) == (2, 2, "FINISHED")
    assert (out.competition == "en.1").sum() == 1
    assert list(out["date"]) == sorted(out["date"])


def test_same_data_is_unchanged():
    df = _base()
    new = _frame([_m(1), _m(2, status="TIMED", home=3, away=4, date="2026-11-25T20:00:00Z")])
    out, changed = replace_block(df, new, "uefa.cl", LABEL)
    assert not changed and out is df


def test_in_play_is_not_a_change():
    df = _base()
    live = _frame([_m(1), _m(2, status="IN_PLAY", hg=1, ag=0, home=3, away=4, date="2026-11-25T20:00:00Z")])
    assert replace_block(df, live, "uefa.cl", LABEL)[1] is False


def test_kickoff_move_is_a_change():
    df = _base()
    moved = _frame([_m(1), _m(2, status="TIMED", home=3, away=4, date="2026-11-26T20:00:00Z")])
    assert replace_block(df, moved, "uefa.cl", LABEL)[1] is True


def test_empty_block_raises():
    with pytest.raises(ValueError, match="no matches"):
        replace_block(_base(), _frame([]), "uefa.cl", LABEL)


def test_cached_teams_used_unless_unknown_id(tmp_path):
    raw = tmp_path / "raw"
    (raw / "2026-11-10").mkdir(parents=True)
    (raw / "2026-11-10" / "CL_2026_teams.json").write_text(json.dumps({"teams": TEAMS[:4]}))
    c = Client([_m(1), _m(2, home=3, away=4)])
    refresh_competition(c, "CL", 2026, _base(), Resolver(), raw_root=raw)
    assert ("teams", "CL", 2026) not in c.calls
    c = Client([_m(1), _m(2, home=5, away=6)])  # 5 and 6 are not in the cached teams
    refresh_competition(c, "CL", 2026, _base(), Resolver(), raw_root=raw)
    assert ("teams", "CL", 2026) in c.calls


def _paths(tmp_path):
    raw, proc, store = tmp_path / "raw", tmp_path / "processed", tmp_path / "snapshots"
    proc.mkdir()
    store.mkdir()
    _base().to_parquet(proc / "matches.parquet", index=False)
    return {"raw_root": raw, "processed_dir": proc, "store_dir": store}


def _write_raw(raw, code, matches):
    d = raw / "2026-11-25"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{code}_2026_matches.json").write_text(json.dumps({"matches": matches}))
    (d / f"{code}_2026_teams.json").write_text(json.dumps({"teams": TEAMS}))


class RawClient(Client):
    """Like the real force client: every fetch also lands in today's raw dir."""

    def __init__(self, raw, matches):
        super().__init__(matches)
        self.raw = raw

    def matches(self, code, year):
        ms = super().matches(code, year)
        _write_raw(self.raw, code, ms)
        return ms


def test_run_refresh_cl_only(tmp_path):
    p = _paths(tmp_path)
    cl = [_m(1), _m(2, hg=3, ag=1, home=3, away=4, date="2026-11-25T20:00:00Z")]
    c = RawClient(p["raw_root"], {"CL": cl, "PL": [_m(900, home=5, away=6)]})
    res = run_refresh(c, now=datetime(2026, 11, 25, 22, tzinfo=UTC), resolver=Resolver(), **p)
    assert res.changed == ["CL"] and res.due == [] and res.any
    assert [k for k, *_ in c.calls] == ["matches"]  # one request, no domestic
    df = pd.read_parquet(p["processed_dir"] / "matches.parquet")
    assert df[df.match_id == "fd:2"].iloc[0].home_goals == 3
    assert json.loads((p["processed_dir"] / "cl_2026_fd.json").read_text()) == cl
    assert [x.name for x in p["processed_dir"].iterdir() if x.name.startswith(".")] == []
    # second run, same data: nothing changes, parquet untouched
    mtime = (p["processed_dir"] / "matches.parquet").stat().st_mtime_ns
    res = run_refresh(c, now=datetime(2026, 11, 25, 22, tzinfo=UTC), resolver=Resolver(), **p)
    assert not res.any
    assert (p["processed_dir"] / "matches.parquet").stat().st_mtime_ns == mtime


def test_run_refresh_domestic_flag(tmp_path, monkeypatch):
    p = _paths(tmp_path)
    monkeypatch.setattr(refresh, "DOMESTIC_FD", {"PL": "en.1"})
    cl = [_m(1), _m(2, status="TIMED", home=3, away=4, date="2026-11-25T20:00:00Z")]
    pl = [_m(900, home=5, away=6, hg=4, ag=4, date="2026-11-22T15:00:00Z")]
    c = RawClient(p["raw_root"], {"CL": cl, "PL": pl})
    res = run_refresh(c, domestic=True, now=datetime(2026, 11, 25, tzinfo=UTC), resolver=Resolver(), **p)
    assert res.changed == ["PL"]
    df = pd.read_parquet(p["processed_dir"] / "matches.parquet")
    assert df[df.match_id == "fd:900"].iloc[0].home_goals == 4


def test_github_output(tmp_path, monkeypatch):
    out = tmp_path / "gh_out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    write_github_output(True)
    write_github_output(False)
    assert out.read_text() == "changed=true\nchanged=false\n"
    monkeypatch.delenv("GITHUB_OUTPUT")
    write_github_output(True)  # no-op without the variable

