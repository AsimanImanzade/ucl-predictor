# Knockout Bracket Reference

Part of `applying-ucl-format-rules`. Verify against the current season's regulations (see "Verification rule" in SKILL.md) before relying on it.

## Knockout play-off pairings (positions 9–24)

League positions form **pairs**. The draw decides which team of a seeded pair meets which team of the matching unseeded pair.

| Seeded pair (2nd leg home) | vs | Unseeded pair |
|---|---|---|
| 9 / 10 | vs | 23 / 24 |
| 11 / 12 | vs | 21 / 22 |
| 13 / 14 | vs | 19 / 20 |
| 15 / 16 | vs | 17 / 18 |

There is no country protection in the knockout phase. Teams from the same association can meet.

## Round of 16 slots

Each top-8 pair is linked to one play-off "pairing pair". The draw decides which of the two top-8 teams gets which of the two play-off winners from that line.

| Top-8 pair (2nd leg home) | meets winners of the ties involving |
|---|---|
| 1 / 2 | 15/16 vs 17/18 |
| 3 / 4 | 13/14 vs 19/20 |
| 5 / 6 | 11/12 vs 21/22 |
| 7 / 8 | 9/10 vs 23/24 |

## Bracket halves

Positions 1 and 2 go to **opposite halves** of the bracket. The same applies to 3 and 4, 5 and 6, and 7 and 8, each split by the draw. So 1 and 2 can only meet in the final, assuming both win their earlier ties.

From the Round of 16 on, the path is fixed: QF, SF and final pairings follow from the bracket built at the draw. There is no new draw per round.

## Home advantage by leg

| Tie | Leg 1 home | Leg 2 home |
|---|---|---|
| Play-off | Unseeded (17–24) | Seeded (9–16) |
| Round of 16 | Play-off winner | Top-8 team |
| QF / SF | Set by the draw | Set by the draw |
| Final | Neutral | — |

The QF/SF leg order comes from the bracket draw, not from seeding. In simulation, randomise it per run unless the real draw has already happened. In that case, load it from data.

## Simulation algorithm (per run)

1. Rank the simulated league table (tiebreakers in SKILL.md).
2. For each play-off line, randomly assign who meets whom inside the paired positions.
3. For each top-8 pair, randomly assign halves and play-off slots.
4. Play each tie: leg 1 → leg 2 → extra time → penalties if needed.
5. Advance the winners through the fixed bracket to the final.
6. Record the furthest stage for each team: `out_league`, `playoff`, `r16`, `qf`, `sf`, `final`, `winner`.

When a real draw has been made, steps 2–3 load the actual draw instead of randomising.

## Test cases to write first

- A 36-row table with a three-way tie on points, resolved at step 3 (away goals).
- 9th and 10th swapping between runs changes the play-off opponent, but only within 23/24.
- 1st and 2nd never meet before the final over 10,000 simulated draws.
- A two-legged tie level on aggregate with equal away goals goes to extra time, not an away-goals winner.

## Simulator conventions

- **Leg order:** play-off, the unseeded side hosts leg 1; R16, the play-off winner hosts leg 1; QF and SF, a coin flip.
- **Final venue 2026/27:** Estadio Metropolitano, `finalVenueTeamId = esp-atletico-madrid`; neutral for everyone else.
- **Missing UEFA coefficient** (newcomers such as Como) defaults to 0, the lowest. It only matters at tiebreak step 10; log it.
