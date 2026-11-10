# Milestone 1: follow-ups

The final whole-branch review of `m1-foundation` (2026-11-10) found no critical defects. These are the items it deferred, grouped by the milestone that must handle them.

## Gate before any numbers are published (before the M2 deploy)

- **Elo league-seeding bias.** Leagues first ingested in 2018-19 (nl, pt, tr, gr, be, sco) are pinned near 1500, because a new top division seeds at 1500 and league averages can only move through sparse European matches.
  - Against Big-5 clubs, their clubs score below their Elo expectation every season since 2019-20, by about −0.06 to −0.22 expected score per match. That is roughly 70 Elo points of overrating.
  - **Fix:** seed leagues from a strength prior (for example country coefficient → Elo offset), or add a league offset or a European-match K boost.
  - **Tests:** add the cross-league residual as a backtest metric and a regression test. Then backtest pre-season league-phase RPS against `elo-dc-v1`.
  - Fold in two related items: the `.1` seeding pool currently includes departed teams, and alpha needs tuning, since it sets the Elo vs team-effect split.
- **Title-odds concentration.** Bayern gets 29.1% pre-season. The model has no rating uncertainty; consider a calibration check and in-simulation rating drift.

## Before M2 (dashboard / browser Worker)

- **Knockout wiring test:** use forced scores to check hosts and the `playoffTie` lookup.
- **Tie tests:** extra time, the level path of `playFinal`, and second-leg host winning on aggregate.
- **Sampler test:** an orientation test with lopsided λ.
- **Input validation in `simulate`:** reject played fixtures with null goals, check the team count, and check that the season and λ `asOf` and team sets agree. Also, `matchday` may be null.
- **Node types:** restrict `@types/node` to the CLI via tsconfig `types`.
- **Display:** the UI shows "<0.1%" / ">99.9%", never 0.0% / 100.0% from rounding.
- **Performance:** profile per-run allocations at 20k runs on a phone.

## Before M3 (cron updater) — blocking

- **Fresh-day ingest is slow:** about 1.5 h. Investigate the football-data pacing and reset-sleep path (the header may be `X-Requests-Available-Minute`). Then fetch only what changed.
- **Same-day cache:** add a force-refresh option. Otherwise a cron run never sees results that come in after the first fetch of the day.
- **Cache writes:** validate JSON before writing the cache, retry on 429, and make cache writes atomic.
- **Silent fallbacks:** warn when a football-data block is empty and openfootball is used silently. Warn when a played fixture is downgraded to unplayed, and add a test for kickoff == as_of.
- **Sim CLI:** don't assume cwd = `sim/`; validate `--runs` / `--seed`; don't run `main()` on import.
- **Toolchain:** pin Node (`engines.node`) and handle pnpm's esbuild build-script approval in CI.
- **Real draws:** add the loader for real knockout draws; the play-off draw is in late January 2027.
- **Token on exceptions:** `requests` exceptions carry `request.headers`, which include the token. Never log exception objects with locals.

## M4 or later

- **Coefficient ids:** cover non-CL clubs (e.g. `ita-s-s-lazio` vs `ita-lazio-roma`), strip trailing spaces, and fix ids that go stale after alias edits.
- **Duplicate-candidate decisions:** record the 12 decisions on the Methodology page.
- **European coverage gaps:** openfootball has no `uefa.el` / `uefa.ecl` for 2025-26 and no 2026-27 qualifiers; consider another source.
- **Name and parse gaps:** the transliteration table is a closed list, and unparsed score text is silently None (on real data only "[cancelled]").
- **Rules record:** add `src/rules/SOURCES.md`, which the format-rules skill requires.
- **Test and skill polish:** weak assertions in a few tests; skill word counts.
