---
name: backtesting-predictions
description: Use when judging whether a match model, rating, feature or parameter (such as time decay) is better or worse, before merging any model change, or when someone asks how accurate or well-calibrated the predictions are.
---

# Backtesting Predictions

## Overview

Without a backtest, "the model improved" is an opinion. A change ships only when walk-forward scores on past seasons are **no worse than the current model's**. The report then sits next to the change.

**REQUIRED SUB-SKILL:** Use superpowers:verification-before-completion. Paste the backtest output; don't summarise it from memory.

## Walk-forward protocol

1. Choose evaluation matches: European competition matches from several past seasons, plus domestic matches when relevant.
2. For each match at kickoff `t`, fit or update with `as_of = t` (or at the start of that matchday) and predict. **Never fit once on everything and score in-sample.**
3. Use fixed random seeds and record the git commit, data snapshot date and parameters.

## Metrics

| Metric | Why | Rule |
|---|---|---|
| **RPS** (ranked probability score) | Respects the W > D > L order | Primary metric. Lower is better |
| Log loss | Punishes confident misses | Secondary |
| Brier score | Easy to explain | Secondary |
| Calibration table | "Says 60%, happens 60%?" | Bins of 10%, observed vs predicted |
| Scoreline log-likelihood | Tests the full matrix | Report it. Don't optimise it alone |

## Baselines in every report

1. Base rates (historical home/draw/away share)
2. Elo-only model
3. Elo + Dixon-Coles (the `elo-dc-v1` baseline), which is what any change must beat.

No bookmaker-odds benchmark in v1: there is no licensed source (football-data.co.uk terms forbid bots). Add one only if a licensed feed appears.

First sanity result (2025-26 league phase, fit as of 2025-09-01): Elo+DC RPS 0.2076 vs base-rate 0.2364.

## Tournament-level check

The 36-team format exists only since 2024/25, so run the full simulator pre-season and at each matchday for those seasons. Report how much probability it gave each team's actual finish (top 8 / 9–24 / out, stage reached). With only a few seasons, treat this as a sanity check, not proof.

## Output

Write `reports/backtest/<date>_<model>.md` with:
- a metrics table vs the baselines
- a calibration table
- the seasons used and the commit hash

Include the delta vs the current model in the commit or PR message.

## Common mistakes

| Mistake | Fix |
|---|---|
| Tuning ξ on the same seasons you report | Tune on early seasons, report on later ones |
| Comparing two models on different match sets | Same matches, same seeds |
| Claiming a win from a 0.0005 RPS difference on 300 matches | Report bootstrap intervals and call small deltas "no change" |
