---
name: modeling-match-outcomes
description: Use when building, fitting, tuning or changing the model that predicts a single match's win/draw/loss probabilities or scoreline distribution, including home advantage, time decay, cross-league team strength, extra time or penalties.
---

# Modeling Match Outcomes

## Overview

The model returns a **scoreline probability matrix** for a match. Win/draw/loss, expected goals and "most likely score" are all derived from that one matrix, so they can never disagree. The simulator samples scores from the same matrix, which makes goal-difference tiebreakers realistic.

**REQUIRED SUB-SKILLS:** Use ingesting-football-data (data must be point-in-time) and backtesting-predictions (no model change ships without it).

## Interface (keep stable; the simulator and dashboard depend on it)

```python
def predict_match(home_id: str, away_id: str, as_of: datetime,
                  neutral: bool = False) -> ScoreMatrix: ...
# ScoreMatrix.p[i, j] = P(home scores i, away scores j), i, j in 0..10, sums to 1
# .outcome() -> (p_home, p_draw, p_away)   .expected_goals() -> (λ_home, λ_away)
```

## Baseline model: Dixon-Coles

- **Ratings:** each team gets an attack and a defence rating. λ_home = exp(attack_h − defence_a + home_adv) and λ_away = exp(attack_a − defence_h).
- **Low-score correction:** the Dixon-Coles ρ term adjusts 0-0, 1-0, 0-1 and 1-1.
- **Time decay:** each match is weighted by exp(−ξ·days_ago). Tune ξ by backtest, not by taste.
- **Cross-league strength:** fit on European competitions plus domestic leagues together, so that leagues connect through European matches. Use club Elo as a prior or feature so that teams with few European matches still get sensible ratings.
- **Home advantage:** fitted, not assumed. It is set to 0 when `neutral=True`.

Gradient boosting or Elo blends may later sit **on top of** this model. Each one must beat it in backtests.

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
