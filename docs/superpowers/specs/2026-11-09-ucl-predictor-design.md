# UCL 2026/27 Predictor — Design Spec

_Status: approved design, 2026-11-09. Source of truth for all milestone plans._

## Context
Build a public, portfolio-grade web app that predicts the 2026/27 Champions League:
- per-match win/draw/loss and exact-score probabilities,
- each team's chances of Top 8, Top 24 (play-off), each knockout stage and the title,
- **pre-season** chances (as of 7 Sep 2026, the day before MD1) and **live** chances that update after every real match,
- a what-if editor for unplayed fixtures; real results replace guesses automatically once played,
- every result, full team season stats, and a night-match "Champions League feeling" UI.

**Season status (verified 2026-11-09):** 36 teams, MD1–MD4 played; MD5 24–25 Nov, MD6 8–9 Dec, MD7 19–20 Jan, MD8 27 Jan. Play-offs in February, R16 in March. **Final: 5 June 2027, Estadio Metropolitano (Madrid), which is Atlético's home ground.** Atlético get home advantage if they reach it.

**Decisions taken with the user (2026-11-09)**
| Topic | Decision |
|---|---|
| Logos | Club crests + footer "Unofficial fan project, not affiliated with UEFA or the clubs" + a **kill switch** (one setting swaps every crest for a colour chip + short code). No UEFA logo, starball or anthem. Original night-match design. |
| Updates | Automatic: GitHub Actions cron → football-data.org → refit → re-simulate → redeploy |
| Hosting / stack | Cloudflare Pages (static), Vite + React + TypeScript; public GitHub repo |
| Audience | Portfolio/CV, so the methodology and accuracy pages are first-class |
| Language | English only |
| What-if | Saved in the browser (localStorage) + "Copy link" share URL |
| Model | Hybrid: our own point-in-time Elo + Dixon-Coles → LightGBM Poisson goals on rich features → Dixon-Coles score matrix |
| Data gap | Free sources plus a fallback: teams without domestic data get a "missing" flag and lean on European results and Elo |
| Build order | Live site early: baseline first, ML model swapped in once it beats the baseline |

## Architecture

```
                GitHub Actions (cron, ~15 min on matchdays + daily)
                ┌──────────────────────────────────────────────────┐
 football-data ►│ pipeline/ (Python, uv)                            │
 openfootball ─►│  ingest → own Elo + features (point-in-time)      │
 UEFA coeffs  ─►│  → model → export λ for every remaining fixture   │
   (cached)     │    and every possible knockout pair               │
                │ sim/ (TypeScript, Node) → official 50k-run update │
                │ commit data JSON only if changed → Pages deploys  │
                └──────────────────────────────────────────────────┘
                                   │ web/public/data/*.json
                                   ▼
            web/ (Vite+React) on Cloudflare Pages
            same sim/ package in a Web Worker → instant what-if
```

**Why this shape:** Cloudflare Pages is static, and what-if needs instant re-simulation. So Python does the heavy ML offline and exports per-pair expected goals (λ). **One simulator implementation (TypeScript)** runs both in the browser and in Node, so official chances and what-if chances can never disagree.

**Repo layout (pnpm workspace + uv):**
```
pipeline/  src/uclpred/{ingest,elo,features,models,export}/  tests/
sim/       src/{rules,table,tiebreak,bracket,tie,simulate}.ts  tests/
web/       src/{pages,components,worker,lib}/  public/data/
data/      reference/{team_aliases.csv,coefficients.csv,team_meta.csv}
           snapshots/2026-27/   (raw/ and cache/ git-ignored)
.github/workflows/{ci.yml,update.yml}
docs/superpowers/specs/2026-11-09-ucl-predictor-design.md
```

## Data sources (researched 2026-11-09)
| Need | Source | Notes |
|---|---|---|
| Live CL fixtures, results, crests | **football-data.org v4, free tier** (`CL`) | Key `X-Auth-Token` stored as GitHub secret `FOOTBALL_DATA_TOKEN`, never in the repo. 10 requests/min; scores slightly delayed. `/standings` 404s for CL, so **we compute the table ourselves**. Required attribution: "Football data provided by the Football-Data.org API". |
| Domestic form (25 teams) | football-data.org free tier: PL, PD, BL1, SA, FL1, DED, PPL | Current season, for the domestic features |
| Domestic form (other 11) | openfootball (CC0) where it has the league; otherwise missing + flag | Bodø/Glimt, Viking, Fenerbahçe, Galatasaray, AEK, Brugge, LASK, Sabah, Shakhtar, Slavia, Slovan |
| Training history | openfootball/champions-league (CC0): CL 2011/12–2025/26, EL/UECL partial; engsoccerdata `champs.csv` for CL 2005–2011 (GPL, fetched, not redistributed); openfootball domestic leagues | No free source has complete EL/UECL history. Coverage is documented. |
| UEFA club coefficients | `comp.uefa.com/v2/coefficients` (2005–2027) | Undocumented endpoint, so fetched once and **cached** in `data/reference/coefficients.csv`. The value used during season S = the final ranking after S-1. |
| Team strength | **Our own Elo**, computed from all ingested results | ClubElo is down (502 / Fixtures API deactivated). Owning the Elo also makes it leak-free by construction. |
| **Not used** | football-data.co.uk (terms forbid bots and ML training); FBref/Understat xG (removed or down) | So there is no bookmaker-odds benchmark and no xG feature in v1 |

**First task of Milestone 1: data coverage audit.** A script prints, for each of the 36 teams: history matches available, domestic data source (or missing), Elo burn-in length and coefficient presence. The output is committed to `reports/coverage.md` and becomes the basis of the Methodology page.

## Match model

**Stage 1 — point-in-time strength (baseline).**
- **Elo:** our own, updated match by match across European and domestic results. Margin-of-victory adjusted, with home advantage. Seeded from the 2005 coefficient rank and burned in.
- **Dixon-Coles:** time-decayed attack/defence ratings.

**Stage 2 — LightGBM Poisson goal model.** Two rows per match (each team's perspective), target = goals scored. Every feature is given for the team **and** the opponent. Training set: European matches (higher weight) + domestic matches, all with point-in-time features.

| Group | Features |
|---|---|
| Strength now | Elo, Elo change over 30 / 90 days, DC attack / defence |
| Domestic form (this season) | position ÷ league size, PPG, GD/game, GF/GA per game, last 5 and last 10 league games (points, GD), home/away split, **games played**, `domestic_missing` flag |
| League context | country coefficient / mean Elo of the league |
| UCL this season | points, GD, games played |
| Pedigree | UEFA coefficient (1-year and 5-year, as of S-1), UCL appearances (all-time, last 10 seasons), historic UCL W/D/L and GF/GA per game, best stage in the last 5 seasons |
| Match context | home / away / neutral, rest days |

**Output:** λ_team, λ_opponent → Dixon-Coles score matrix (0..10, ρ fitted) → W/D/L, exact scores, expected goals.

**Anti-misleading safeguards**
1. **Reliability features** (games played, `domestic_missing`), so the model learns how much to trust early or missing form.
2. **Monotone constraints** where direction is certain: higher own Elo ⇏ fewer goals; higher opponent Elo ⇏ more goals.
3. **Form-vs-pedigree scenario tests** (pytest): the same high-coefficient team with a bad current season (bottom-half domestic, losing streak, falling Elo) must get a lower λ than with a good one.
4. **Ablation backtests:** pedigree-only, form-only and full models, reported side by side.
5. **SHAP "why"** on each match page (top factors).

**Gate:** the ML model replaces the baseline only if walk-forward RPS (ranked probability score) improves beyond noise vs Elo+DC. Benchmarks: base rates, Elo-only, Elo+DC (no bookmaker odds; see Data sources).

## Tournament simulator (sim/)
- Follows the applying-ucl-format-rules skill: 36-team table, full tiebreak chain, play-off and R16 pairings, bracket halves, two legs + extra time + penalties, final (home advantage if Atlético).
- Inputs: fixtures, real results (fixed), what-if results (fixed), λ table. Output per team: P(position 1..36), Top 8, 9–24, out, and P(reaching PO, R16, QF, SF, final, winner).
- Seeded RNG. 50k runs for official numbers; about 20k in the browser Worker (target < 2 s on a phone). Real knockout draws are loaded from data once made.
- Not in scope for v1: in-simulation rating drift ("hot" simulation).

## Dashboard (web/)
| Page | Content |
|---|---|
| **Table** (home) | Live table: P, W, D, L, GF, GA, GD, Pts, last-5 form; Top 8 %, Top 24 %, Winner %; toggle Pre-season / After MD n / Live / My scenario |
| **Matches** | Every result by matchday; upcoming fixtures with W/D/L bars and the 3 most likely scores |
| **What-if** | Score inputs for unplayed fixtures. Played fixtures lock automatically, and a saved guess for a now-played match is dropped with a notice. Instant re-simulation with ± deltas vs live. localStorage + "Copy link" |
| **Knockout odds** | Every team × stage (PO, R16, QF, SF, Final, Winner); the real bracket once drawn |
| **Team** | Crest, season stats, matches, chance history across snapshots, key features (Elo, coefficient, domestic position and form) |
| **Match** | Score heatmap, W/D/L, most likely scores with %, SHAP top factors |
| **Methodology & accuracy** | Data coverage, model, backtest results, calibration chart, known limits |

Design per the designing-matchnight-ui and frontend-design skills. Tokens are confirmed with the user via screenshots before pages are built. Every page has the footer disclaimer and the football-data.org attribution. The crest kill switch is `VITE_SHOW_CRESTS`.

## Live updates (update.yml)
1. Cron every 15 min in matchday windows (Tue/Wed/Thu 16:00–23:00 UTC), daily otherwise, plus `workflow_dispatch`.
2. Fetch CL matches. If nothing has changed, exit.
3. If changed: update results and features → predict λ → Node sim (50k) → `web/public/data/live.json`. When a matchday completes, also write the immutable `snapshots/2026-27/mdNN.json`. `md00` = pre-season, rebuilt retroactively with `as_of` = 2026-09-07.
4. Validate (144 league fixtures, 8 per team, Σ Top 8 = 8, Σ winner = 1, no unknown teams) → commit `data: …` → Cloudflare Pages builds from the push.

## Milestones (each gets its own implementation plan via writing-plans)
1. **Foundation:** scaffold, coverage audit, ingest (football-data.org, openfootball, engsoccerdata, coefficients), team aliases, own Elo + Dixon-Coles baseline, TS simulator with rules tests (TDD), CLI printing pre-season and live Top 8 / Top 24 / winner %.
2. **Dashboard:** all pages on the baseline model, Web Worker what-if, deployed to Cloudflare Pages.
3. **Automation:** update.yml + ci.yml, snapshot history, per-match live updates.
4. **ML model:** full feature set, LightGBM Poisson, safeguards, backtests + ablations, SHAP, Methodology page; swapped in only if it passes the gate.

## Skill updates (inside the milestones)
- ingesting-football-data: replace ClubElo / football-data.co.uk with the sources above, plus the terms notes.
- modeling-match-outcomes: own Elo instead of ClubElo; the LightGBM layer and its safeguards.
- backtesting-predictions: no odds benchmark in v1; benchmarks = base rates, Elo, Elo+DC.
- designing-matchnight-ui: crests allowed with the disclaimer and kill switch; UEFA marks remain banned.
- running-matchday-update: per-match `live.json` alongside immutable per-matchday snapshots.
- applying-ucl-format-rules: 2026/27 final venue = Atlético's ground.

## Verification
- CI on every push: `uv run pytest` (no-leak `as_of` tests, scenario tests, export schema) and `pnpm -r test` (tiebreak, bracket, tie resolution, what-if lock-in logic).
- Real-data sanity: Σ P(Top 8) = 8.00, Σ P(winner) = 1, played results never resampled, clinched/eliminated flags match the real table, MD1–MD4 table matches the published results.
- `reports/backtest/…md`: RPS / log loss / calibration vs benchmarks, plus ablations.
- UI: `pnpm --filter web dev`; check every page in the browser pane at 375 px and desktop; screenshot-based design review; what-if lock-in tested by flipping a fixture to played in test data; kill switch tested.
- Deploy: the Cloudflare Pages URL loads, and `live.json`'s timestamp updates after a manual `workflow_dispatch` run.


## What the user must do (cannot be done for them)
- Register a free football-data.org API key and add it as GitHub secret `FOOTBALL_DATA_TOKEN`.
- Create or connect the Cloudflare Pages project to the GitHub repo (in their Cloudflare account).
