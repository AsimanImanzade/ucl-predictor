# Champions League 2026/27 predictor

A prediction pipeline for the 2026/27 UEFA Champions League. A Python package (`pipeline/`, managed with uv) ingests results, fits an Elo and Dixon-Coles match model and exports forecasts; a TypeScript Monte Carlo simulator (`sim/`, pnpm workspace) plays out the league phase and knockouts.

## Setup

```sh
cd pipeline && uv sync     # Python 3.13 environment
pnpm install               # from the repo root
```

Create a git-ignored `.env` in the repo root with `FOOTBALL_DATA_TOKEN=<your football-data.org API token>`.

Tests: `cd pipeline && uv run pytest` and `pnpm --filter @uclpred/sim test`.

Football data provided by the Football-Data.org API
