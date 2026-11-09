---
name: applying-ucl-format-rules
description: Use when writing or changing anything that ranks the 36-team league phase, breaks ties on points, builds the knockout bracket, pairs play-off or Round of 16 ties, or resolves two-legged ties, extra time and penalties in the tournament simulator.
---

# Applying UCL Format Rules

## Overview

The simulator is only as correct as its rules. A perfect match model with one wrong tiebreaker or bracket pairing produces confidently wrong top-8 / top-24 / title probabilities. **Rules live in one module, are tested first, and every rule cites its source.**

**REQUIRED SUB-SKILL:** Use superpowers:test-driven-development. Every rule below gets a failing test with a hand-built table or bracket before any code.

## Format at a glance (2024/25 onward)

| Stage | Who | Shape |
|---|---|---|
| League phase | 36 teams | 8 matches each (4 home, 4 away, 2 opponents per pot), one table, 3/1/0 points |
| Direct to Round of 16 | Positions 1–8 | Seeded; play 2nd leg at home |
| Knockout play-off ("1/16") | Positions 9–24 | Two legs; 9–16 seeded (2nd leg at home) vs 17–24 |
| Eliminated | Positions 25–36 | No drop into another competition |
| R16 → QF → SF | 16 → 2 | Two legs, fixed bracket from the league positions + draw |
| Final | 2 | One match, neutral venue |

## League-phase tiebreakers (equal points)

Applied in order, **across all tied teams at once** (not head-to-head):

1. Goal difference
2. Goals scored
3. Away goals scored
4. Wins
5. Away wins
6. Points won collectively by the team's league-phase opponents
7. Collective goal difference of those opponents
8. Collective goals scored by those opponents
9. Fewer disciplinary points (red = 3, yellow = 1)
10. UEFA club coefficient

In simulation, disciplinary points are unknown. Skip step 9 and fall through to the coefficient, and note this in code. Steps 6–8 need the *whole simulated table*, so compute them after every match in that simulation is played.

## Bracket and tie resolution

Pairings, seeding sides and the draw are in [bracket-reference.md](bracket-reference.md). Read it before you touch the bracket code.

Two-legged tie: aggregate score → if level, 30 min extra time in leg 2 (no away-goals rule) → if still level, penalties. Final: 90 min → extra time → penalties.

## Verification rule

UEFA can amend regulations between seasons. Before a season's first simulation:
- Check the current *UEFA Champions League Regulations* (league-phase ranking and knockout articles).
- Record the season, article numbers and date checked in `src/rules/SOURCES.md`.
- If anything differs from this skill, update the skill **and** its tests in the same change.

## Common mistakes

| Mistake | Fix |
|---|---|
| Head-to-head tiebreak (old group-stage habit) | League phase uses the overall criteria above |
| Away-goals rule in knockout ties | Abolished. Level aggregate → extra time |
| One fixed bracket per simulation run | The draw is random. Re-draw sides/pairs inside **every** simulation |
| Showing 0% / 100% from rounding | Only when mathematically clinched/eliminated. Otherwise "<0.1%" / ">99.9%" |
| Sorting the table with Python's default tuple sort and forgetting "fewer is better" for discipline | Explicit sort key per criterion with its direction |
