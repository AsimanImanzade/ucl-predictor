---
name: running-matchday-update
description: Use when a Champions League matchday or knockout round has finished, when new real results need to flow into forecasts, when producing the pre-season (matchday 0) snapshot, or when asked what changed since the last matchday.
---

# Running a Matchday Update

## Overview

Each matchday produces one **immutable snapshot**: the probabilities exactly as they stood after that round. The dashboard's "before any games" and "after matchday N" views, and its trend charts, all read from these snapshots. **Never overwrite a past snapshot. Fix forward with a new version.**

## Steps

1. **Ingest results** for the round (ingesting-football-data). Run the validation: every finished fixture has a score, and there are no unknown team ids.
2. **Freeze `as_of`** at the last kickoff of the round + 1 day.
3. **Refit or update** the match model with that `as_of` (modeling-match-outcomes).
4. **Simulate** the remainder of the tournament, at least 50,000 runs with a recorded seed (applying-ucl-format-rules).
5. **Save** `data/snapshots/<season>/md<NN>.parquet`. Matchday 0 = pre-season, then md01…md08 and knockout rounds `po`, `r16`, `qf`, `sf`, `final`. Save `md<NN>.meta.json` alongside it with the commit, seed, run count, model version and `as_of`.
6. **Diff vs the previous snapshot** and write `reports/matchday/<season>_md<NN>.md`. Include each team's top 8 / top 24 / R16 / QF / SF / final / winner %, the five biggest movers each way, and newly clinched or eliminated teams.
7. **Verify before announcing:** the snapshot loads, the probabilities per stage sum correctly (Σ P(winner) = 1, and Σ P(top 8) = 8), and the clinched/eliminated flags agree with the real table.

## Monte Carlo noise

With N = 50,000, a 50% probability has a standard error of about 0.22 percentage points. Moves under ~0.5 pp are noise and are not called "movers".

## Common mistakes

| Mistake | Fix |
|---|---|
| Re-simulating already-played matches | Played results are fixed inputs, never sampled |
| Different seed/N between snapshots, then comparing tiny moves | Keep N and the seed policy fixed. Respect the noise floor |
| Pre-season snapshot built with ratings from after matchday 1 | `as_of` = day before the first league-phase kickoff |
| Editing md03 after md04 exists | Write `md03.v2` and record why in meta |
