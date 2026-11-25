# Champions League 2026/27 Predictor

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![pandas](https://img.shields.io/badge/pandas-150458?style=flat-square&logo=pandas&logoColor=white) ![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn&logoColor=white) ![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white) ![React](https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB) ![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white) ![Cloudflare Pages](https://img.shields.io/badge/Cloudflare_Pages-F38020?style=flat-square&logo=cloudflare&logoColor=white)

Forecasts the 2026/27 UEFA Champions League: every team's chance of a top-8 finish, the play-offs and each knockout round, updated after every matchday. Unofficial fan project.

**Live dashboard: [asiman-ucl-predictor.pages.dev](https://asiman-ucl-predictor.pages.dev)**

## Results

After matchday 4 (50,000 simulated seasons, seed 1):

| Team | Win the final | Top 8 |
|---|---|---|
| Bayern | 20.6% | 83.0% |
| Arsenal | 16.9% | 88.8% |
| Barcelona | 16.4% | 80.1% |
| PSG | 13.1% | 93.6% |
| Real Madrid | 10.0% | 96.7% |

The default model `elo-dc-v2.1` was chosen in a pre-registered evaluation: settings and pass marks were fixed before the run, and the run happened once. It is scored with the ranked probability score (RPS, lower is better) against the earlier `elo-dc-v1`.

| Check | v1 | v2.1 | Pass mark | Result |
|---|---|---|---|---|
| League gap, mid-league vs Big-5 clubs in Europe, 2022-26 (n=284) | -0.152 | -0.021 | \|gap\| ≤ 0.03 | Pass |
| RPS, European matches 2022-26 (n=2,390) | 0.2089 | 0.2096 | ΔRPS CI upper ≤ +0.003 | Pass |
| RPS, holdout across all competitions (n=589) | 0.1983 | 0.1996 | ΔRPS CI upper ≤ +0.006 | Pass |

- A plain Elo rating overrated clubs from mid-sized leagues (Netherlands, Portugal, Turkey, Belgium and others) against Big-5 clubs: their actual Elo score in those matches was 0.15 per match below the expected score. The league-aware Elo cuts that bias by 86%.
- That fix costs almost no accuracy: the 95% bootstrap intervals on the RPS change include zero.
- An earlier attempt, `elo-dc-v2`, failed its own pre-registered checks and was not adopted. Its verdict is kept in [reports/calibration.md](reports/calibration.md).

Full record: [reports/v21-evaluation.md](reports/v21-evaluation.md).

## Data

66,607 finished matches from July 2010 to November 2026 across 23 competitions: the three European cups and their qualifiers, plus the top divisions of England, Spain, Germany, Italy, France, the Netherlands, Portugal, Belgium, Turkey, Scotland, Austria and Greece, and four second divisions. Sources:

| Source | Use | Licence / terms |
|---|---|---|
| [openfootball](https://github.com/openfootball) champions-league TXT and football.json | Historical European and domestic results | CC0 (public domain) |
| [football-data.org](https://www.football-data.org) free tier | Live Champions League and current/previous domestic results | Free-tier terms; attribution required (below); max 10 requests/min |
| UEFA club coefficients endpoint | Tiebreak step 10 and seeding context | Fetched once and cached; used only for ranking values |

ClubElo and football-data.co.uk are not used (their terms do not allow bots or ML training); Elo is computed in-house. Team names are matched across sources through an alias table with a guard that fails on unknown or ambiguous names. Coverage per team is in [reports/coverage.md](reports/coverage.md).

## Method

1. **Point-in-time ratings:** every feature for a match is built only from matches finished before its kick-off, so past forecasts can be scored honestly.
2. **League-aware Elo:** each club's rating is its league's level plus its own offset. Domestic matches move only the offsets. European matches count double and mostly move the league levels, so results in Europe carry over to every club in that league.
3. **Goal model:** a weighted Poisson regression on Elo difference plus team attack and defence, with home advantage, a four-year window and time decay (older matches count less, European matches count double). A Dixon-Coles correction adjusts low-scoring results.
4. **Tournament simulation:** a TypeScript Monte Carlo simulator plays the remaining fixtures 50,000 times. It ranks the 36-team league phase with UEFA's tiebreak rules, draws the play-off and Round of 16 bracket, and resolves two-legged ties with extra time and penalties.
5. **Backtesting:** a grid search on 2019-22, then a report on 2022-26 with bootstrap confidence intervals, calibration bins and a check of past whole tournaments.

## Dashboard

A static site with no server. Pages: Table, Matches, Match, Team, Knockout odds, What-if and Methodology. The What-if page runs the same simulator code in a Web Worker: set any score and 20,000 seasons rerun in the browser. Snapshots before matchday 1 and after each matchday show how the chances moved.

## Run it

```sh
cd pipeline && uv sync     # Python 3.13 environment
pnpm install               # from the repo root
```

Create a git-ignored `.env` in the repo root:

```
FOOTBALL_DATA_TOKEN=<your football-data.org API token>
```

Never commit `.env`. The token is read only from the environment and is never logged or cached.

Run the Python commands from `pipeline/`:

```sh
uv run uclpred ingest                          # fetch + cache sources, build data/processed/matches.parquet
uv run uclpred coefficients --season-year 2026 # UEFA club coefficients for the season
uv run uclpred coverage                        # data coverage report (reports/coverage.md)
uv run uclpred export --as-of 2026-09-07 --out data/export/md00   # pre-season (matchday 0) snapshot
uv run uclpred export --as-of now --out data/export/live          # current state
uv run uclpred ingest --processed-only         # no network: rebuild processed files from cached raw data
uv run uclpred backtest                        # grid search + v1 vs v2 -> reports/calibration.md
uv run uclpred tournament-check [--runs 50000] # past-season tournament check
uv run uclpred evaluate-v21                    # run-once pre-registered v2.1 evaluation -> reports/v21-evaluation.md
```

`export` takes `--season` (default 2026-27) and `--model` (`elo-dc-v2.1` default; `elo-dc-v1` and `elo-dc-v2` stay available).

Simulate from the repo root (official runs: 50,000 runs, seed 1):

```sh
pnpm --filter @uclpred/sim cli -- --input data/export/live [--runs 50000] [--seed 1] [--sigma 70] [--out file.json]
```

`--sigma` sets rating uncertainty in Elo points; `--out` writes the chances JSON to the given path.

## Live updates

`.github/workflows/update.yml` keeps the site current. A small Cloudflare Worker (`scheduler/`) starts it every 15 minutes on Tuesday to Thursday from 16:00 to 23:45 UTC and once a day at 06:00 UTC (this run also re-fetches the domestic leagues), because GitHub's own cron is best-effort and once skipped a whole match night. The workflow keeps a daily GitHub schedule as a backup and can be run on demand ("Run workflow", with optional `force` and `domestic`). Each run:

1. `uclpred refresh` fetches the current Champions League season from football-data.org in one request, always live (never today's cached copy). Only results, kick-off times and pairings count as changes; a match in play does not. If nothing changed, the run stops here.
2. `uclpred update` (no network) exports `live`, and an `mdNN` snapshot for each newly complete matchday from the first run after midnight UTC following its last kick-off. It runs the official simulation for each (50,000 runs, seed 1, sigma 0), then `build-data`.
3. The site is built and deployed to Cloudflare Pages (direct upload). `web/public/data` and `data/snapshots` are committed as `data: live update …`.

Snapshots in `data/snapshots/2026-27/` are immutable: `build-data` adds new ones and refuses to overwrite one. The git-ignored `data/raw` and `data/processed` live in the GitHub Actions cache, because football-data's data is not republished as a dump here. A new cache entry is saved only after a successful deploy, so a failed run is retried by the next one. On a cache miss, the workflow runs the full `uclpred ingest` once (about 5 minutes in CI).

Repository secrets (Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `FOOTBALL_DATA_TOKEN` | your football-data.org API token |
| `CLOUDFLARE_API_TOKEN` | a Cloudflare API token with the *Cloudflare Pages: Edit* permission |
| `CLOUDFLARE_ACCOUNT_ID` | your Cloudflare account id |

The scheduler Worker needs a fine-grained GitHub token limited to this repository with *Actions: Read and write*:

```sh
cd scheduler
npx wrangler@4.160.0 deploy                     # cron triggers from wrangler.toml
npx wrangler@4.160.0 secret put GITHUB_TOKEN    # paste the token at the prompt
node --test worker.test.js
```

The same update by hand, from the repo root:

```sh
(cd pipeline && uv run uclpred refresh)     # [--domestic]; prints what changed and which snapshots are due
(cd pipeline && uv run uclpred update)      # export live + due mdNN, 50k sims, build-data
pnpm --filter @uclpred/web build            # tsc + vite build -> web/dist
npx wrangler@4.160.0 pages deploy web/dist --project-name asiman-ucl-predictor --branch main
```

Lower-level steps:

```sh
(cd pipeline && uv run uclpred export --as-of now --out data/export/live)
pnpm --filter @uclpred/sim cli -- --input data/export/live --runs 50000 --seed 1 --sigma 0   # writes chances.json there
(cd pipeline && uv run uclpred calibration-bins)        # reports/calibration-bins-v21.json
pnpm --filter @uclpred/web build-data [mdNN ...] live   # stored snapshots + these exports -> web/public/data
pnpm --filter @uclpred/web dev                          # http://localhost:5173
```

Snapshot dates are the day after each matchday's last kick-off (md01 2026-09-11, md02 2026-10-15, md03 2026-10-22, md04 2026-11-05); md00 is 2026-09-07. `VITE_SHOW_CRESTS=false` builds the site without club crests.

Tests and checks:

```sh
cd pipeline && uv run ruff check . && uv run pytest && uv run pytest -m data
pnpm -r test
pnpm --filter @uclpred/sim exec tsc --noEmit
pnpm --filter @uclpred/web exec tsc --noEmit
node --test scheduler/worker.test.js live/worker.test.js
```

Tests marked `data` need the local data caches; tests marked `network` need the network. Both are skipped by default. `.github/workflows/ci.yml` runs the default tests, ruff and the web build on every push to `main`.

## Live scores

While a game is on, the Matches and Match pages show a red **LIVE** badge (or **HT** at half time) with the current score, and **FT** once football-data has the final score but the update workflow has not yet counted it. They are display only: the odds, the table and the what-if lab use `live.json`, which counts a game only once it is finished.

The scores come from a second Cloudflare Worker, `live/` (`ucl-predictor-live`). Cloudflare's Cache API does nothing on `*.workers.dev`, so visitors never reach football-data. Instead a cron runs every minute on Tuesday to Thursday from 16:00 to 23:59 UTC. It asks football-data for today's matches only when a game is on, a kick-off is less than 5 minutes away, or it is the first check of the day, and it saves the result in Workers KV only when something changed. `GET /` reads KV and returns today's games that are in play, at half time or finished (`{date, updatedAt, matches: [{id, status, home, away}], attribution}`). That is at most one football-data request a minute, however many people are watching. CORS allows only the Pages site. The dashboard polls once a minute from kick-off to 2 h 30 after it, only while the tab is visible.

One-time setup, from `live/`:

```sh
npx wrangler@4.160.0 kv namespace create LIVE              # put the printed id in wrangler.toml
npx wrangler@4.160.0 secret put FOOTBALL_DATA_TOKEN        # paste the football-data token at the prompt
npx wrangler@4.160.0 deploy                                # prints the workers.dev URL
```

The site reads the URL from `LIVE_URL` in `web/src/lib/config.ts`; `VITE_LIVE_URL` overrides it, and an empty value turns live scores off.

## Files

| Path | Purpose |
|---|---|
| `pipeline/` | Python package `uclpred`: ingestion, team matching, Elo, goal model, backtests, exports |
| `sim/` | TypeScript Monte Carlo simulator: league table, UEFA tiebreaks, bracket, two-legged ties |
| `web/` | React dashboard and in-browser what-if (Vite) |
| `data/reference/` | Team aliases, club coefficients and fitted model parameters |
| `data/snapshots/` | Immutable per-matchday snapshots (assembled dashboard JSON) |
| `.github/workflows/` | `ci.yml` (tests) and `update.yml` (live updates and deploys) |
| `scheduler/` | Cloudflare Worker whose cron triggers start `update.yml` |
| `live/` | Cloudflare Worker that serves live scores to the dashboard (display only) |
| `reports/` | Coverage, calibration and evaluation reports |

Football data provided by the Football-Data.org API
