---
name: ingesting-football-data
description: Use when fetching, caching, cleaning or joining match results, fixtures, Elo ratings, xG or betting odds; when team names don't match across sources; or when a feature might contain information from after a match's kickoff (data leakage, look-ahead bias).
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
  fixtures/<season>.csv            # league-phase fixture list
```

## Candidate sources (check terms before use)

| Need | Source | Notes |
|---|---|---|
| European + domestic results, odds | football-data.co.uk CSVs | Closing odds are the benchmark for backtesting |
| Daily club Elo | clubelo.com API | Point-in-time by date, so it's leakage-safe |
| Fixtures / results | openfootball, UEFA site | Cross-check the league-phase fixture list |
| xG | Understat or another provider | Coverage varies by league. Check robots.txt and terms |

Respect each site's terms and robots.txt, rate-limit requests, and cache raw downloads so they are fetched once.

## Rules

1. **Canonical team ids.** Every source name maps through `team_aliases.csv` to a `team_id` (e.g. `inter`, `psg`). An unmapped name **fails the run** and is listed. It is never dropped or fuzzy-matched silently.
2. **Point-in-time.** Every feature row carries `as_of` (UTC). A prediction for a match at kickoff `t` may only use rows with `as_of < t`. Ratings are snapshotted per date, never the "latest" value.
3. **Raw is immutable.** Fixes happen in transform code, so the pipeline is reproducible from `data/raw/`.
4. **Validate after every load.** No duplicate matches, scores are non-negative integers, and every league-phase team has exactly 8 fixtures (4 home, 4 away). The league phase has 144 matches in total.
5. **Neutral venues are flagged** (`neutral=True`), so the model doesn't add home advantage to a final.

## Common mistakes

| Mistake | Fix |
|---|---|
| Joining on raw names ("Man City" vs "Manchester City") | Always join on `team_id` |
| Using today's Elo for a 2019 match | Join ratings on the date before kickoff |
| Odds recorded after kickoff | Use closing odds only, with a timestamp before kickoff |
| Re-downloading everything each run | Cache by date in `data/raw/` |
