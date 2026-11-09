---
name: ingesting-football-data
description: Use when fetching, caching, cleaning or joining match results, fixtures, UEFA coefficients or team ratings; when team names don't match across sources; or when a feature might contain information from after a match's kickoff (data leakage, look-ahead bias).
---

# Ingesting Football Data

## Overview

Every probability the project shows comes from this data. Two failures matter most: **team-name mismatches** silently drop matches, and **look-ahead leakage** makes backtests look great and live forecasts bad. **Every row knows when it was knowable.**

## Directory contract

```
data/
  raw/<source>/<YYYY-MM-DD>/...    # exactly as downloaded, never edited (git-ignored)
  reference/team_aliases.csv       # source, source_name, team_id   (committed)
  processed/matches.parquet        # one row per match, canonical ids
  processed/ratings.parquet        # team_id, as_of, rating columns
```

## Sources (v1)

| Need | Source | Notes |
|---|---|---|
| Live CL results, current + previous domestic | football-data.org free tier | CL 2024-2026; PL/PD/BL1/SA/FL1/DED/PPL. Token from env `FOOTBALL_DATA_TOKEN` (never log or cache it). 10 req/min (sleep >= 6.5 s). Keep the attribution line. CL `/standings` returns 404, so compute the table ourselves |
| Historical European results | openfootball champions-league TXT | cl/clq/el/elq/conf/confq, 2011-12..2025-26 (CC0) |
| Historical domestic results | openfootball football.json | CC0 |
| Club coefficients | UEFA coefficients endpoint (cached) | Value for season S = final ranking after S-1. Country codes are FIFA-style |

**Removed:** ClubElo (we compute our own Elo, see modeling-match-outcomes) and football-data.co.uk (terms forbid bots and ML training). No licensed odds source exists in v1. Respect terms and robots.txt, rate-limit, cache raw downloads.

## Rules

1. **Canonical team ids.** Every source name maps through `team_aliases.csv` to a `team_id` (e.g. `ita-inter`, `esp-atletico-madrid`). An unmapped name **fails the run** and is listed. It is never dropped or fuzzy-matched silently.
2. **Point-in-time.** Every feature row carries `as_of` (UTC). A prediction for a match at kickoff `t` may only use rows with `as_of < t`. Ratings are snapshotted per date, never the "latest" value.
3. **Raw is immutable.** Fixes happen in transform code, so the pipeline is reproducible from `data/raw/`.
4. **Validate after every load.** No duplicate matches, scores are non-negative integers, and every league-phase team has exactly 8 fixtures (4 home, 4 away). The league phase has 144 matches in total.
5. **Neutral venues are flagged** (`neutral=True`), so the model doesn't add home advantage to a final.

6. **Details** (alias CSV curation checklist, year-less date inference, 90-minute goals from football-data and openfootball): read [details.md](details.md) before touching `ingest/` or `team_aliases.csv`. Keys are FIFA codes plus exact `core_name()` output; never merge distinct clubs; football-data `fullTime` includes shoot-out goals, so use `regularTime`.
7. **Fail loud.** Any non-404 fetch error raises after the loop; a silently missing competition-season corrupts Elo.
8. **Undetermined fixtures** (null team ids, knockout rounds before the draw) are skipped. A non-null id missing from the team map raises.
9. **Not a gap:** 2019-20 had single-leg QF/SF after Covid (119 CL matches, not 125).

## Common mistakes

| Mistake | Fix |
|---|---|
| Joining on raw names ("Man City" vs "Manchester City") | Always join on `team_id` |
| Using today's Elo for a 2019 match | Join ratings on the date before kickoff |
| Re-downloading everything each run | Cache by date in `data/raw/` |
