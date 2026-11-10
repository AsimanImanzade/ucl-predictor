# Calibration step: outcome and follow-ups

**Outcome (2026-11-10):**
- **Gate FAIL** on criteria 1, 2 and 3. The default model stays `elo-dc-v1` and nothing was switched.
- **Tooling landed:** league-aware Elo, the backtest harness, rating uncertainty, the past-season tournament check, and the recorded verdict.
- **Full evidence:** `reports/calibration.md`.

## Recommended next step (from the final review)

Do not switch to v2 as it stands, and do not re-tune on 2022-26 (those seasons have already been looked at). Instead, run one small **pre-registered v2.1 round**. If it fails, ship the dashboard (M2) on v1 with a visible caveat.

**Fix before running anything:**
- **Identity:** merge `aut-red-bull-salzburg` into `aut-rb-salzburg` (and correct the `AUT,salzburg,…` alias), `ita-ss-lazio` into `ita-lazio-roma`, and `por-vitoria` into `por-vitoria-guimaraes`. Add a probe that fails when a Euro-only id belongs to a country whose league is in the data, or when an export team has too few prior matches.
- **Missing domestic data:** backfill be/gr/sco/tr for 2021-22 – 2023-24 if a licensed source has it.
- **Fixed settings for the run:**
  - alpha fixed at 0.005, not tuned (the tuned 0.0005 did not transfer);
  - no pooling for `.x` pseudo-leagues (g = 0 for Euro-only clubs);
  - keep the chosen (k, k_euro, g) for real leagues;
  - σ = 0 (no σ helped). Re-parametrise the noise before reusing it, because it acts only through `eloCoef`.

**Revised gates, written down before running:**
1. League gap within ±0.03 over 2022-26.
2. ΔRPS CI upper ≤ +0.003. This is sized from the CI half-width, so an equally good model can pass.
3. Tournament check as a sanity bound only.
4. User review of md00.
- Use 2026-27 matches played since 2026-09-07 as the only clean holdout.

**Separate change:** treat home advantage on its own. Both models under-predict home wins on 2022-26 by about 4.2 points, which comes from the shared GLM home term.

## Deferred items by when they matter

**Before the next calibration run**
- In `actual_outcomes`, the `expected=None` path is used only by toy fixtures. Keep the production call strict.
- The v2 real-data test bound (`test_league_gap_real.py`) has only a 0.003 margin and will flip once the data is fixed.
- Report the team-season bootstrap for the tournament check as a computed number instead of a quoted diagnostic.
- The bootstrap resamples matches independently, but legs of one tie and matches sharing a monthly fit are correlated. Consider resampling by tie.

**Before M2 uses σ > 0**
- Record σ and `eloCoef` in `SimResult` / `chances.json`.
- Reject `--runs` values of 0 or below.
- Document that σ > 0 drops the Dixon-Coles ρ correction.
- Test noise on a partly played season.

**Before M2 (any model)**
- Regenerate md00/live and the `reports/m1-first-run.md` tables. The local exports predate the alias fixes (λ shifts up to ~1.2%).
- Keep the M1 follow-ups in `docs/superpowers/m1-followups.md`.

**Test hygiene (later)**
- Elo v2 tests:
  - vacuous assertion `test_elo_v2.py:145-147`;
  - relegation and peer-seeded switches untested;
  - seeding boundary (exactly 3 peers, not own peer) untested;
  - the mean − 150 vs 1350 fallback isn't told apart;
  - weak same-kickoff assertion.
- Guard against non-league domestic codes before a cup competition is ingested.
- Metrics and backtest:
  - duplicate `match_id` errors and NA/NaN checks;
  - `bool(NaN)` for `neutral`;
  - empty-frame bootstrap;
  - the walk-forward stub encodes only the month;
  - chained-tie boundary test for `select_params`.
- `merge_report` treats `## ` inside fenced code as a heading.
