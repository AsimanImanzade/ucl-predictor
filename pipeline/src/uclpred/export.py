"""Snapshot export: season.json (teams + fixtures) and lambdas.json (match rates)."""

import json
import logging
import math
from datetime import UTC, datetime
from pathlib import Path

from uclpred.config import FINAL_VENUE_TEAM, MODEL_NAME, SEASON
from uclpred.ingest.football_data import PLAYED_STATUSES, normalize_fd_match

log = logging.getLogger(__name__)

LAMBDA_MIN, LAMBDA_MAX = 0.05, 6.0


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_season(fd_matches, fd_teams, resolver, coefs, as_of: datetime) -> dict:
    team_country = {t["id"]: t["area"]["code"] for t in fd_teams}
    teams, fd_to_id = [], {}
    for t in fd_teams:
        tid = resolver.resolve(t["area"]["code"], t["name"])
        fd_to_id[t["id"]] = tid
        if tid not in coefs:
            log.warning("no UEFA coefficient for %s; using 0.0", tid)
        teams.append({
            "id": tid,
            "fdId": t["id"],
            "name": t["name"],
            "shortName": t["shortName"],
            "tla": t["tla"],
            "crest": t["crest"],
            "country": tid.split("-", 1)[0].upper(),
            "coefficient": float(coefs.get(tid, 0.0)),
        })  # fmt: skip
    teams.sort(key=lambda t: t["id"])

    fixtures = []
    league = [m for m in fd_matches if m.get("stage") == "LEAGUE_STAGE"]
    for m in sorted(league, key=lambda m: (m["utcDate"], m["id"])):
        kickoff = datetime.fromisoformat(m["utcDate"])
        played = m["status"] in PLAYED_STATUSES and kickoff < as_of
        hg = ag = None
        if played:
            norm = normalize_fd_match(m, team_country)
            if norm is not None and norm.home_goals is not None:
                hg, ag = int(norm.home_goals), int(norm.away_goals)
            else:
                played = False
        fixtures.append({
            "id": m["id"],
            "matchday": m.get("matchday"),
            "utcDate": m["utcDate"],
            "homeId": fd_to_id[m["homeTeam"]["id"]],
            "awayId": fd_to_id[m["awayTeam"]["id"]],
            "played": played,
            "homeGoals": hg,
            "awayGoals": ag,
        })  # fmt: skip
    return {
        "season": SEASON,
        "asOf": iso_utc(as_of),
        "finalVenueTeamId": FINAL_VENUE_TEAM,
        "teams": teams,
        "fixtures": fixtures,
    }


def warn_unrated_teams(model, team_ids: list[str]) -> list[str]:
    """Warn (never fail) for teams with no pre-as_of Elo or no training-window matches."""
    flagged = []
    for t in team_ids:
        problems = []
        if t not in model.ratings:
            problems.append("no Elo rating before as_of (mean rating used)")
        if t not in model.attack:
            problems.append("no matches in the model's training window")
        if problems:
            flagged.append(t)
            log.warning("%s: %s", t, "; ".join(problems))
    return flagged


def build_lambdas(model, team_ids: list[str]) -> dict:
    def matrix(venue: str):
        return [
            [
                None if a == b else [float(x) for x in model.lambdas(a, b, venue)]
                for b in team_ids
            ]
            for a in team_ids
        ]

    return {
        "asOf": iso_utc(model.as_of),
        "model": MODEL_NAME,
        "rho": float(model.rho),
        "teams": list(team_ids),
        "home": matrix("home"),
        "neutral": matrix("neutral"),
    }


def validate_snapshot(season: dict, lambdas: dict) -> None:
    problems: list[str] = []
    teams = [t["id"] for t in season["teams"]]
    if len(teams) != 36 or len(set(teams)) != 36:
        problems.append(f"expected 36 distinct teams, got {len(teams)}")
    fixtures = season["fixtures"]
    if len(fixtures) != 144:
        problems.append(f"expected 144 fixtures, got {len(fixtures)}")
    home: dict[str, int] = dict.fromkeys(teams, 0)
    away: dict[str, int] = dict.fromkeys(teams, 0)
    for f in fixtures:
        if f["homeId"] not in home or f["awayId"] not in away:
            problems.append(f"fixture {f['id']} references unknown team")
            continue
        home[f["homeId"]] += 1
        away[f["awayId"]] += 1
    for t in teams:
        if home[t] != 4 or away[t] != 4:
            problems.append(f"{t}: {home[t]} home / {away[t]} away fixtures (need 4/4)")
    if lambdas["teams"] != teams:
        problems.append("team order differs between season.json and lambdas.json")
    n = len(lambdas["teams"])
    for key in ("home", "neutral"):
        mat = lambdas[key]
        if len(mat) != n or any(len(r) != n for r in mat):
            problems.append(f"lambda matrix {key} is not {n}x{n}")
            continue
        for i, row in enumerate(mat):
            for j, cell in enumerate(row):
                if i == j:
                    if cell is not None:
                        problems.append(f"{key}[{i}][{j}] diagonal must be null")
                    continue
                if cell is None or len(cell) != 2:
                    problems.append(f"{key}[{i}][{j}] lambda missing")
                    continue
                for v in cell:
                    if not (math.isfinite(v) and LAMBDA_MIN <= v <= LAMBDA_MAX):
                        problems.append(f"{key}[{i}][{j}] lambda {v} out of range")
    if problems:
        raise ValueError("invalid snapshot:\n" + "\n".join(problems[:50]))


def write_snapshot(season: dict, lambdas: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, obj in (("season.json", season), ("lambdas.json", lambdas)):
        (out / name).write_text(
            json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )


def run_export(as_of: datetime, out: Path) -> str:
    import pandas as pd

    from uclpred.config import PROCESSED, REFERENCE
    from uclpred.elo import run_elo
    from uclpred.matches import load_matches
    from uclpred.models.baseline import fit_baseline
    from uclpred.teams import TeamResolver

    fd_matches = json.loads((PROCESSED / "cl_2026_fd.json").read_text(encoding="utf-8"))
    fd_teams = json.loads(
        (PROCESSED / "cl_2026_teams.json").read_text(encoding="utf-8")
    )
    cdf = pd.read_csv(REFERENCE / "coefficients.csv")
    cdf = cdf[cdf["season_year"] == 2026]
    coefs = dict(zip(cdf["team_id"], cdf["total_5y"].astype(float), strict=True))

    matches = load_matches()
    elo = run_elo(matches)
    model = fit_baseline(matches, elo, as_of)
    season = build_season(fd_matches, fd_teams, TeamResolver(), coefs, as_of)
    team_ids = [t["id"] for t in season["teams"]]
    warn_unrated_teams(model, team_ids)
    lambdas = build_lambdas(model, team_ids)
    validate_snapshot(season, lambdas)
    write_snapshot(season, lambdas, out)
    vals = [
        v
        for key in ("home", "neutral")
        for row in lambdas[key]
        for cell in row
        if cell
        for v in cell
    ]
    played = sum(f["played"] for f in season["fixtures"])
    return (
        f"as_of: {season['asOf']}\n"
        f"played fixtures: {played}/{len(season['fixtures'])}\n"
        f"lambda min/max: {min(vals):.3f} / {max(vals):.3f}  -> {out}"
    )
