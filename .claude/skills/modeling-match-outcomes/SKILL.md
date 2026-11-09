---
name: modeling-match-outcomes
description: Use when building, fitting, tuning or changing the model that predicts a single match's win/draw/loss probabilities or scoreline distribution, including home advantage, time decay, cross-league team strength, extra time or penalties.
---

# Modeling Match Outcomes

## Overview

The model returns a **scoreline probability matrix** for a match. Win/draw/loss, expected goals and "most likely score" are all derived from that one matrix, so they can never disagree. The simulator samples scores from the same matrix, which makes goal-difference tiebreakers realistic.

**REQUIRED SUB-SKILLS:** Use ingesting-football-data (point-in-time data) and backtesting-predictions (no model change ships without it).

## Interface (keep stable; the simulator and dashboard depend on it)

```python
model.predict_match(home_id, away_id, neutral=False) -> np.ndarray  # p[i, j], 0..10, sums to 1
model.lambdas(team_a, team_b, venue)  # venue "home" (a hosts) | "neutral" -> (λ_a, λ_b)
```
`uclpred.models.score_matrix` derives outcome, expected goals and most-likely score from the one matrix. The exporter hands the simulator per-pair λ for each venue.

## Own Elo (`uclpred.elo`)

Replaces ClubElo. Single chronological pass over 90-minute results, point-in-time (only kickoff `< as_of`). K 20, home advantage 60 (0 at neutral venues), margin-of-victory multiplier. Seeding on a team's first appearance: in a `uefa.*` match, the mean of that country's already-rated teams if there are >= 3, else 1400; in a `.2` league, 1350; in a `.1` league, that competition's rated-peer mean if >= 5 peers, else 1500. Both teams of a match are seeded before either is registered. Burn-in is 2010-11 domestic and 2011-12 European data.

## Baseline `elo-dc-v1`

Poisson GLM (weighted, ridge):

`log λ = μ + h·home + β·Δelo/100 + attack(team) + defence(opp)`

- Time decay xi 0.0019/day, 4-year window; `euro_weight` 2 for `uefa.*` matches; ridge `alpha` 0.005.
- Dixon-Coles rho is fitted separately with bounds, adjusting 0-0, 1-0, 0-1, 1-1.
- Leagues connect through European matches; Elo carries cross-league strength. `alpha` sets the split between the Elo term and team effects, so tune it by backtest.
- Home advantage is fitted, and not applied when neutral.

**Known calibration issues (fix before trusting public numbers):** pre-season title odds are over-concentrated (Bayern 29.7%, max λ 5.4). Elo gets inflated by domestic dominance for clubs in weaker leagues. M4 should backtest alpha, calibration, and possibly in-simulation rating drift.

Gradient boosting or Elo blends may later sit **on top of** this model, and each must beat it in backtests.

## Knockout extras

| Situation | Approach |
|---|---|
| Extra time (30 min) | Poisson with rates λ × 30/90 |
| Penalties | ~50/50. Tilt slightly by rating only if backtests support it |
| Two-legged tie | Simulate both legs independently. Aggregate is handled by applying-ucl-format-rules |

## Rules

- **No look-ahead.** Fitting with `as_of = t` only sees matches before `t`. Assert this in code.
- **Seeds.** Every fit and simulation takes an explicit random seed, so results reproduce.
- **Version artifacts.** Save fitted parameters to `models/<model_name>/<as_of>.json` with the git commit and backtest scores.
- **Honest output.** These are calibrated estimates, not "exact" probabilities. The dashboard says so once, plainly.

## Common mistakes

| Mistake | Fix |
|---|---|
| Truncating the matrix at 5 goals so it sums < 1 | Use 0..10 and renormalise |
| Independent Poisson draws in the simulator but Dixon-Coles in the UI | Both sample from the same `ScoreMatrix` |
| Treating "most likely score" as a prediction | Show it with its probability (often ~10–13%) |
