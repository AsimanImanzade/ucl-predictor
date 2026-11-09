# Champions League 2026/27 predictor

A prediction pipeline for the 2026/27 UEFA Champions League. A Python package (`pipeline/`, managed with uv) ingests results, builds its own Elo ratings, fits a Dixon-Coles style match model (`elo-dc-v1`) and exports forecasts. A TypeScript Monte Carlo simulator (`sim/`, pnpm workspace) plays out the league phase and knockouts.

Design: [docs/superpowers/specs/2026-11-09-ucl-predictor-design.md](docs/superpowers/specs/2026-11-09-ucl-predictor-design.md). Run reports: [reports/](reports/) (`coverage.md`, `m1-first-run.md`).

## Setup

```sh
cd pipeline && uv sync     # Python 3.13 environment
pnpm install               # from the repo root
```

Create a git-ignored `.env` in the repo root:

```
FOOTBALL_DATA_TOKEN=<your football-data.org API token>
```

Never commit `.env`. The token is read only from the environment and is never logged or cached.

## Commands

Run the Python commands from `pipeline/`.

```sh
uv run uclpred ingest                          # fetch + cache sources, build data/processed/matches.parquet
uv run uclpred coefficients --season-year 2026 # UEFA club coefficients for the season
uv run uclpred coverage                        # data coverage report (reports/coverage.md)
uv run uclpred export --as-of 2026-09-07 --out data/export/md00   # pre-season (matchday 0) snapshot
uv run uclpred export --as-of now --out data/export/live          # current state
```

Simulate from the repo root (official runs: 50,000 runs, seed 1):

```sh
pnpm --filter @uclpred/sim cli -- --input data/export/live [--runs 50000] [--seed 1]
```

Tests and checks:

```sh
cd pipeline && uv run ruff check . && uv run pytest && uv run pytest -m data
pnpm --filter @uclpred/sim test
pnpm --filter @uclpred/sim exec tsc --noEmit
```

Tests marked `data` need the local data caches; tests marked `network` need the network. Both are skipped by default.

## Data sources and licences

| Source | Use | Licence / terms |
|---|---|---|
| [openfootball](https://github.com/openfootball) champions-league TXT and football.json | Historical European and domestic results | CC0 (public domain) |
| [football-data.org](https://www.football-data.org) free tier | Live Champions League and current/previous domestic results | Free-tier terms; attribution required (below); max 10 requests/min |
| UEFA club coefficients endpoint | Tiebreak step 10 and seeding context | Fetched once and cached; used only for ranking values |

ClubElo and football-data.co.uk are not used (their terms do not allow bots / ML training); Elo is computed in-house.

Football data provided by the Football-Data.org API
