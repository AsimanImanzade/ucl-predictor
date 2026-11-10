# Calibration step — Design Spec

_Status: approach A approved by the user (2026-11-10). Gate before any numbers are published (before the M2 deploy). Parent spec: `2026-11-09-ucl-predictor-design.md`._

## Context

The Milestone 1 final review measured a structural bias in the Elo used by `elo-dc-v1`:

- **Cause.** A league that first appears in the data (nl/pt/tr/gr/be/sco/at.1 from 2018-19) seeds its first clubs at a flat 1500 and later newcomers at the league mean. Domestic matches are zero-sum, so a league's level can only move through its few European matches.
- **Gap.** Clubs from those leagues under-perform their Elo expectation against Big-5 clubs. The average shortfall in expected score is **−0.159** per match over 2019-20 onwards (n = 419), roughly 100 Elo points.
- **Effect on the md00 table:** Sporting ≈ Real Madrid, PSV/Porto above Liverpool/Atlético, and Atlético at 0.3% to win.
- **Separate concentration.** Bayern's pre-season title share is 29%. The simulator treats strengths as exact, with no rating uncertainty.

A throwaway probe compared variants on real data (2019-20+ European matches):

| Variant | Gap vs Big-5 | Euro Brier |
|---|---|---|
| Current | −0.159 | 0.1672 |
| European K × 2 | −0.125 | 0.1655 |
| League-aware, untuned (g = 0.8) | −0.037 | 0.1692 |

League-aware Elo removes the bias but needs tuning to stay accurate, so tuning decides.

## Goals

1. A league-aware Elo (`elo-v2`) that removes the cross-league bias without losing match-level accuracy.
2. A reusable backtest harness (walk-forward, standard metrics, bootstrap CIs) that this and every later model change goes through.
3. Rating uncertainty in the simulator, so title odds reflect what we don't know.
4. A recorded gate decision in `reports/calibration.md`. If the gate passes, the default model switches to `elo-dc-v2` and md00/live are regenerated.

**Non-goals:** the LightGBM feature model (M4), odds benchmarks, xG, the dashboard.

## Design

### 1. League-aware Elo (`pipeline/src/uclpred/elo_v2.py`)

**Rating.** `rating(club, t) = L[league(club, t)] + o[club]`.

- `league(club, t)` is the competition code of the club's most recent domestic match before t.
- A club with no domestic match yet belongs to the country pseudo-league `"<cty>.x"` (e.g. `"aze.x"`), so Euro-only clubs of one country share a level.

**Updates**, with Δ = K · k_mult · MOV · (S − E) as today:

- **Domestic match:** offsets only (`o_h += Δ`, `o_a −= Δ`). League levels never move from domestic results.
- **European match, clubs in different leagues:** `L_h += g·Δ`, `L_a −= g·Δ`, `o_h += (1−g)·Δ`, `o_a −= (1−g)·Δ`.
- **European match, same league:** offsets only.
- `k_mult = k_euro` for `uefa.*` matches, 1 otherwise.

**Initialisation.**

- **New league level `L`:** the mean current rating of that country's already-rated clubs if ≥ 3 exist. Otherwise 1500 for `.1`, 1350 for `.2` and 1400 for `.x`.
- **New club:** `o = 0` (it starts at its league's level).

**Continuity.** When a club's league changes (promotion, relegation, or first domestic match after Euro-only history), its total rating is preserved: `o_new = (L_old + o_old) − L_new`.

**Interface.**

- `run_elo_v2(matches, params: EloV2Params) -> EloResult`, the same `EloResult` (`pre`, `rating_as_of`, `ratings_as_of`) as v1, so `fit_baseline` uses it unchanged.
- `EloV2Params`: `k=20, k_euro=1.5, g=0.7, home_adv=60` (defaults; the backtest picks the final values).
- v1 stays in place for comparison.

**Point-in-time** semantics are identical to v1: strictly before `as_of`, with the same sort order.

### 2. Backtest harness (`pipeline/src/uclpred/backtest.py`, CLI `uclpred backtest`)

**Walk-forward.**

- Evaluation matches: all FINISHED `uefa.*` matches in the evaluation seasons.
- Checkpoints on the 1st of every month: refit the goal model with `as_of = checkpoint`, then predict that month's matches.
- Elo is computed once per Elo-parameter set over all data. This is leak-free because only `pre` and `rating_as_of` are used.

**Season split.**

- Tuning seasons: 2019-20, 2020-21, 2021-22.
- Report seasons: 2022-23, 2023-24, 2024-25, 2025-26.
- Parameters are chosen only on tuning seasons. Report seasons are scored once with the chosen parameters.

**Metrics.**

- RPS (primary), log loss and Brier on W/D/L from the score matrix.
- A calibration table: home-win probability in 10 bins, observed vs predicted.
- **League gap:** mean (actual − expected) Elo score for mid-league clubs vs Big-5 clubs, 2019-20+.
  - Mid leagues: nl, pt, tr, gr, be, sco, at (`.1`).
  - Big-5: en, es, de, it, fr (`.1`).
  - Club labels come from the club's latest domestic competition in that season.
- **Bootstrap:** a 95% CI for ΔRPS vs `elo-dc-v1` on identical matches, from 1,000 match resamples with seed 1.

**Grid** (27 Elo parameter sets × 3 alpha = 81 models):

- `k ∈ {16, 20, 24}`
- `k_euro ∈ {1.0, 1.5, 2.0}`
- `g ∈ {0.5, 0.7, 0.9}`
- GLM `alpha ∈ {0.0005, 0.002, 0.005}`

The model with the best tuning-season RPS wins. Ties within 0.0005 RPS go to the smaller league gap.

**Output:** `reports/calibration.md`, with the grid top-10, the chosen parameters, report-season metrics for v1 vs v2 (with CI), the calibration table, the league gap for v1 vs v2, the tournament check (§4) and the gate verdict.

### 3. Rating uncertainty in the simulator (`sim/`)

**Export.** `lambdas.json` gains `eloCoef` (the GLM β per 100 Elo) and `ratingSigma` (Elo points; 0 means off). The TS `Lambdas` type adds both as optional; missing means σ = 0, so old files behave as today.

**Per run, when σ > 0:**

1. Draw `n_t ~ Normal(0, σ)` for every team from the seeded RNG (Box-Muller).
2. Each match uses `λ_a' = λ_a · exp(β·(n_a − n_b)/100)` and `λ_b' = λ_b · exp(β·(n_b − n_a)/100)`.
3. Goals are sampled as independent Poisson (fitted ρ ≈ −0.01, so the Dixon-Coles correction is negligible; documented).

When σ = 0, the existing cached Dixon-Coles path is used unchanged. Fixed and played results never change.

**Choosing σ:** σ ∈ {0, 40, 70, 100}, picked by the tournament check (§4). If results are flat within noise, prefer 70 as a prior. Report the choice.

### 4. Tournament check (past seasons)

- **Export past seasons.** `uclpred export --season 2024-25|2025-26 --as-of <day before that season's MD1>`, built from the cached football-data CL 2024 and 2025 data. The function stays the same; season, fixtures, teams and final venue become parameters.
  - 2024-25 final: Munich → `finalVenueTeamId = "ger-bayern-munchen"`.
  - 2025-26: Budapest → `null`.
- **Score the simulations** (50k runs per σ) against what actually happened:
  - log loss of each team's actual stage reached, over {out, po, r16, qf, sf, final, winner};
  - Brier score on Top 8 and Top 24;
  - for each model (v1, v2) × σ.
- **Concentration measure:** the largest pre-season title share in each season.

### 5. Gate and switch

**Gate.** It passes only if all of these hold:

1. League gap within ±0.03 for v2.
2. Report-season ΔRPS (v2 − v1): the upper bound of its 95% CI is ≤ +0.001 (no worse beyond noise).
3. Tournament log loss for v2 with the chosen σ is ≤ v1 with σ = 0, averaged over both seasons.
4. The user reviews the regenerated 2026-27 md00 table.

**If it passes:** `MODEL_NAME = "elo-dc-v2"`. Export uses v2 with the chosen parameters and σ. Regenerate md00/live. Update `reports/m1-first-run.md`, remove its "not for publication" caveat (after criterion 4), and update the modeling and backtesting skills.

**If it fails:** record why in `reports/calibration.md`, keep v1, and stop to discuss.

## Testing

**Elo v2 unit tests:**

- Domestic matches never change any `L`.
- A European cross-league match moves `L` by exactly `g·Δ`.
- Promotion keeps the total rating continuous.
- A Euro-only club joins its `.x` pseudo-league.
- Point-in-time: `pre` equals `rating_as_of`, excluding that match.
- Seeding from country peers.

**Backtest unit tests** (synthetic):

- RPS, log loss and Brier values.
- Checkpoint windows never include matches on or after the checkpoint.
- The bootstrap is deterministic with a seed.
- The league-gap metric on a hand-built example.

**Simulator tests:**

- σ = 0 gives byte-identical results to the current simulator for the same seed.
- σ > 0 lowers the max title share on a synthetic season.
- Determinism by seed.
- Old `lambdas.json` files without the new fields still load.

**Export tests:** a past-season export validates (144 league fixtures, 4H/4A), and its final venue is set per season.

**Real-data checks** (`@pytest.mark.data`): the v2 league gap is within ±0.03, and a backtest smoke run completes on one season.
