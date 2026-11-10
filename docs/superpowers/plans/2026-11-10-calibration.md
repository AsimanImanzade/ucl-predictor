# Calibration Step Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the cross-league Elo bias with a league-aware Elo (`elo-v2`), add rating uncertainty to the simulator, and prove both with a walk-forward backtest and a past-season tournament check. The result is a recorded gate verdict.

**Architecture:**
- **Python, `pipeline/`:** gains `elo_v2.py` (same `EloResult` interface as v1), `backtest.py` (walk-forward + metrics + bootstrap), multi-season export with a `--model` switch, and a tournament-check driver.
- **TypeScript, `sim/`:** gains an optional per-run rating-noise path driven by two new optional `lambdas.json` fields.
- **Shared parameters:** the chosen parameters live in one committed file, `data/reference/model_params.json`.

**Tech Stack:** Python 3.13 (uv, pandas, numpy, scipy, scikit-learn, pytest, ruff); Node 24 / TypeScript 5 strict (pnpm 10, vitest, tsx).

**Spec:** `docs/superpowers/specs/2026-11-10-calibration-design.md`, with parent spec `docs/superpowers/specs/2026-11-09-ucl-predictor-design.md`. Follow the project skills `modeling-match-outcomes`, `backtesting-predictions` and `applying-ucl-format-rules`.

## Global Constraints

- All Milestone 1 rules still hold:
  - point-in-time: only kickoff `< as_of`;
  - 90-minute goals only;
  - team id `<cty>-<slug>`;
  - never print, log or commit `.env` / `FOOTBALL_DATA_TOKEN`;
  - explicit seeds;
  - unit tests never touch the network; `@pytest.mark.data` / `network` are opt-in.
- **Model names:** `elo-dc-v1` (current, unchanged) and `elo-dc-v2` (league-aware Elo + same GLM).
- **`EloV2Params` defaults:** `k=20.0, k_euro=1.5, g=0.7, home_adv=60.0, init_top=1500.0, init_second=1350.0, init_unknown=1400.0`.
- **Pseudo-league for clubs without domestic data:** `"<cty>.x"`, where `cty` is the lowercase id prefix, e.g. `"aze.x"`.
- **Season split:** tuning seasons are `2019-20, 2020-21, 2021-22`; report seasons are `2022-23, 2023-24, 2024-25, 2025-26`. Parameters are chosen on tuning seasons only.
- **Grid:** `k ∈ {16, 20, 24}`, `k_euro ∈ {1.0, 1.5, 2.0}`, `g ∈ {0.5, 0.7, 0.9}`, `alpha ∈ {0.0005, 0.002, 0.005}`. GLM `xi=0.0019, window_days=1460, euro_weight=2.0` stay fixed.
- **Selection:** the lowest tuning-season mean RPS wins. Ties within 0.0005 go to the smaller |league gap|.
- **League gap:**
  - mid leagues are `{nl.1, pt.1, tr.1, gr.1, be.1, sco.1, at.1}`; Big-5 are `{en.1, es.1, de.1, it.1, fr.1}`;
  - computed over European matches from season `2019-20` onwards;
  - value = mean (actual − expected Elo score) from the mid-league club's side;
  - a club's label is its latest domestic competition in that season.
- **Bootstrap:** 1,000 resamples of match ids, seed 1, 95% percentile CI.
- **σ grid (Elo points):** `{0, 40, 70, 100}`. If tournament log losses lie within 0.01 of each other, choose 70.
- **Seasons table** (in `uclpred.config.SEASONS`):

  | season | fd_year | preseason_as_of (UTC) | final_venue_team |
  |---|---|---|---|
  | `2024-25` | 2024 | `2024-09-16T00:00:00Z` | `ger-bayern-munchen` |
  | `2025-26` | 2025 | `2025-09-15T00:00:00Z` | `null` |
  | `2026-27` | 2026 | `2026-09-07T00:00:00Z` | `esp-atletico-madrid` |
- **Coefficient `season_year` for season `YYYY-YY`:** the start year YYYY (e.g. 2024-25 uses 2024).
- **Gate thresholds:**
  1. |league gap v2| ≤ 0.03;
  2. the upper bound of the 95% CI of report-season ΔRPS (v2 − v1) ≤ +0.001;
  3. mean tournament log loss over both past seasons for v2 at the chosen σ ≤ v1 at σ = 0;
  4. user review of the md00 table.
- **New `lambdas.json` fields:** `eloCoef` (number, GLM β per 100 Elo) and `ratingSigma` (number, Elo points). Both are optional in TS; missing means σ = 0.

## Review Focus

1. **A promoted or relegated club** (changes `.2` ↔ `.1`) must keep its total rating across the move. A jump would corrupt every promoted side. Test in Task 1.
2. **A club with European history before its league enters the data** (e.g. PSV before nl.1 2018-19) must keep its total rating when it first appears domestically. Test in Task 1.
3. **An old `lambdas.json` without `eloCoef` / `ratingSigma`** must still simulate, with σ = 0, byte-identically to today. Test in Task 6.
4. **Walk-forward checkpoints** must cover every month with European matches, including July/August qualifiers and the August 2020 finals, and never include a match on or after its checkpoint. Test in Task 3.
5. **v1 and v2 compared on different match sets** would bias ΔRPS. The bootstrap must align on identical `match_id`s and fail if the sets differ. Test in Task 3.

---

### Task 1: League-aware Elo (`elo_v2.py`)

**Files:**
- Create: `pipeline/src/uclpred/elo_v2.py`, `pipeline/tests/test_elo_v2.py`, `pipeline/tests/test_elo_v2_real.py`

**Interfaces:**
- Consumes: the canonical matches DataFrame (`load_matches()`); `EloResult`, `expected_home` and `mov_multiplier` from `uclpred.elo`.
- Produces:
  - `@dataclass EloV2Params` (the defaults in Global Constraints)
  - `run_elo_v2(matches: pd.DataFrame, params: EloV2Params | None = None) -> EloResult`, with the same `pre` columns and `rating_as_of` semantics as v1
  - `run_elo_v2` returns `EloV2Result(EloResult)`, which adds `league_levels_as_of(as_of: datetime) -> dict[str, float]` (league code → level, strictly before `as_of`). The report uses it.

- [ ] **Step 1: Write the failing tests** (synthetic frames, built with the helpers style from `tests/test_elo.py`):
  - `test_domestic_match_never_moves_league_level`: after any `xx.1` match, every league level is unchanged.
  - `test_cross_league_euro_match_moves_levels_by_g`: a `uefa.cl` match between a `aaa.1` club and a `bbb.1` club moves `L[aaa.1]` by exactly `g·Δ` and `L[bbb.1]` by `−g·Δ`. Each club's total moves by Δ.
  - `test_same_league_euro_match_moves_offsets_only`.
  - `test_promotion_keeps_total_rating`: a club plays in `aaa.2`, then its first `aaa.1` match. Its pre-match rating for that first `.1` match equals its last post-match rating from `.2` (to 1e-9).
  - `test_euro_history_then_first_domestic_keeps_total`: a club plays `uefa.clq`, so it sits in pseudo-league `aaa.x`. When it then plays `aaa.1`, its total is unchanged.
  - `test_euro_only_club_uses_country_pseudo_league`: two euro-only `zzz-` clubs share `L["zzz.x"]`.
  - `test_new_league_seeded_from_country_peers`: with ≥ 3 already-rated `aaa-` clubs, the first `aaa.1` match sets `L[aaa.1]` to their mean rating. With fewer than 3, `aaa.1` → 1500, `aaa.2` → 1350, `aaa.x` → 1400.
  - `test_k_euro_multiplier`: the same result in `uefa.el` changes the totals by `k_euro`× the domestic delta.
  - `test_point_in_time_pre_equals_rating_as_of`: as in v1, and SCHEDULED rows are ignored.
- [ ] **Step 2: Run** `cd pipeline && uv run pytest tests/test_elo_v2.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `run_elo_v2` as a single chronological pass over FINISHED rows sorted by `(date, match_id)`.
  - Keep `L: dict[str,float]`, `o: dict[str,float]` and `league_of: dict[str,str]` (initial `"<cty>.x"`).
  - Before each match, move each club whose current domestic competition differs from `league_of` using the continuity rule. Seed any unseen league first.
  - A pre-match rating is `L[league_of[t]] + o[t]`.
  - Apply the update rules from spec §1.
  - Record per-club `(date, total_after)` for `EloResult`, plus league-level history for `league_levels_as_of`.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Real-data smoke check** (`test_elo_v2_real.py`, `@pytest.mark.data`): `run_elo_v2(load_matches())` completes in under 10 s. As of 2026-09-07 it rates `esp-real-madrid`, `eng-liverpool` and `esp-atletico-madrid` above `ned-psv`; print those four ratings. Run with `uv run pytest -m data tests/test_elo_v2_real.py -v -s`.
- [ ] **Step 6: Commit:** `feat(pipeline): league-aware Elo (elo-v2)`

---

### Task 2: Metrics (log loss, Brier, calibration table, league gap)

**Files:**
- Modify: `pipeline/src/uclpred/models/metrics.py`
- Create: `pipeline/tests/test_metrics.py`

**Interfaces:**
- Consumes: the existing `rps(probs, outcomes)`.
- Produces:
  - `log_loss(probs: np.ndarray, outcomes: np.ndarray, eps: float = 1e-12) -> float`: mean −log p of the observed outcome.
  - `brier(probs: np.ndarray, outcomes: np.ndarray) -> float`: mean Σ_k (p_k − 1[k = o])².
  - `calibration_table(p_home: np.ndarray, home_won: np.ndarray, bins: int = 10) -> pd.DataFrame` with columns `bin_lo, bin_hi, n, mean_pred, observed`.
  - `league_gap(matches: pd.DataFrame, elo_pre: pd.DataFrame, home_adv: float, from_season: str = "2019-20") -> tuple[float, int]`, returning (mean residual from the mid-league side, n). Mid/Big-5 sets, labels and the season filter are exactly as in Global Constraints; expected scores come from `expected_home` (0 home advantage when neutral).

- [ ] **Step 1: Write the failing tests:**
  - `log_loss([[1,0,0]],[0]) ≈ 0` (clipped);
  - `log_loss([[0.5,0.25,0.25]],[1]) == -log(0.25)`;
  - `brier([[1/3]*3],[0]) == (4/9+1/9+1/9)`;
  - a calibration table of 4 synthetic predictions lands in the right bins with the right observed rates;
  - `league_gap` on a hand-built frame (two seasons, one mid-league and one Big-5 club, one European match each way with known pre ratings) returns the hand-computed residual and n = 2, and ignores matches before `from_season`.
- [ ] **Step 2: Run** `uv run pytest tests/test_metrics.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Real-data check** (`tests/test_league_gap_real.py`, `@pytest.mark.data`):
  - `league_gap` with v1 (`run_elo`, home_adv 60) is < −0.10 (the probe gave −0.159);
  - with v2 defaults (`run_elo_v2`) |gap| < 0.06 (the probe gave −0.037).
  Print both values.
- [ ] **Step 6: Commit:** `feat(pipeline): log loss, Brier, calibration table and league-gap metrics`

---

### Task 3: Walk-forward backtest engine + bootstrap

**Files:**
- Create: `pipeline/src/uclpred/backtest.py`, `pipeline/tests/test_backtest.py`

**Interfaces:**
- Consumes: `fit_baseline(matches, elo, as_of, alpha=…)`, `BaselineModel.predict_match`, `outcome_probs`, and the Task 2 metrics.
- Produces:
  - `monthly_checkpoints(dates: pd.Series) -> list[pd.Timestamp]`: 00:00 UTC on the 1st of every month from the month of the first date up to and including the month after the last date.
  - `walk_forward(matches: pd.DataFrame, elo: EloResult, seasons: list[str], alpha: float) -> pd.DataFrame`, with columns `match_id, season, p_home, p_draw, p_away, outcome` (0 home, 1 draw, 2 away).
    - Evaluation rows are FINISHED `uefa.*` matches in `seasons`.
    - For each consecutive checkpoint pair `[c_i, c_{i+1})`: fit once at `as_of = c_i`, then predict the matches with `c_i ≤ date < c_{i+1}`, using `neutral` from the row.
  - `score(preds: pd.DataFrame) -> dict` with keys `rps, log_loss, brier, n`.
  - `bootstrap_delta_rps(a: pd.DataFrame, b: pd.DataFrame, n_boot: int = 1000, seed: int = 1) -> tuple[float, float, float]`, returning (mean Δ = rps(b) − rps(a), lo, hi). Raises `ValueError` if the `match_id` sets differ.

- [ ] **Step 1: Write the failing tests:**
  - `test_checkpoints_cover_summer_and_august_finals`: dates spanning 2019-07-09 … 2020-08-23 give checkpoints from 2019-07-01 to 2020-09-01 inclusive, and every date falls in exactly one `[c_i, c_{i+1})`.
  - `test_walk_forward_never_uses_match_on_or_after_checkpoint`: monkeypatch `fit_baseline` to record its `as_of` and the max training date. For every prediction, the fit's `as_of` ≤ the match date and all training dates are < `as_of`.
  - `test_bootstrap_deterministic_and_aligned`: the same inputs and seed give identical results, and differing `match_id` sets raise `ValueError`.
  - `test_score_keys`: values match the Task 2 functions on a tiny frame.
- [ ] **Step 2: Run** `uv run pytest tests/test_backtest.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Keep `walk_forward` free of I/O. The model is fitted once per checkpoint, not per match.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit:** `feat(pipeline): walk-forward backtest engine with bootstrap`

---

### Task 4: Grid search, params file and the backtest report (real run)

**Files:**
- Modify: `pipeline/src/uclpred/backtest.py`, `pipeline/src/uclpred/cli.py`
- Create: `data/reference/model_params.json`, `reports/calibration.md`, `pipeline/tests/test_backtest_grid.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:
  - `run_grid(matches, tuning_seasons, grid) -> pd.DataFrame`, one row per (k, k_euro, g, alpha) with columns `rps, log_loss, brier, league_gap`. Elo v2 is computed once per Elo-parameter set and reused across alphas.
  - `select_params(grid_df) -> dict`, implementing the selection rule in Global Constraints.
  - `model_params.json`:
    `{"elo-dc-v2": {"elo": {"k","k_euro","g","home_adv"}, "alpha", "rating_sigma": null}, "chosen_on": "<ISO date>", "tuning_seasons": […]}`
    `rating_sigma` stays null until Task 7.
  - `load_model_params() -> dict` (in `backtest.py`).
  - CLI `uclpred backtest`: runs the grid on the tuning seasons and selects. It then scores v1 (`run_elo`, alpha 0.005) and the chosen v2 on the report seasons, computes the bootstrap Δ and the league gaps for v1 and v2, writes `model_params.json`, and writes the report sections "Grid (top 10)", "Chosen parameters", "Report seasons: v1 vs v2" (rps / log_loss / brier / n, plus Δ with its CI), "Calibration (v2)" and "League gap".
- [ ] **Step 1: Write the failing tests:** `select_params` picks the lowest RPS, and breaks a tie (within 0.0005) by smaller |league_gap|. `run_grid` on a tiny synthetic frame with a 2-point grid returns 2 rows with the expected columns (monkeypatch the expensive parts if needed).
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Real run.** Run `uv run uclpred backtest` in the background with a generous timeout. Expected: it finishes in roughly 5–15 minutes and prints the chosen parameters and v1/v2 report-season metrics. Paste the numbers into the task report.
- [ ] **Step 6: Commit:** `feat(pipeline): backtest grid, chosen elo-dc-v2 params and calibration report` (includes `model_params.json` and `reports/calibration.md`).

---

### Task 5: Multi-season export with `--model`

**Files:**
- Modify: `pipeline/src/uclpred/config.py`, `pipeline/src/uclpred/ingest/run.py`, `pipeline/src/uclpred/export.py`, `pipeline/src/uclpred/cli.py`, `pipeline/tests/test_export.py`

**Interfaces:**
- Consumes: `load_model_params()` (Task 4), `run_elo_v2` (Task 1), existing export functions.
- Produces:
  - `config.SEASONS: dict[str, dict]`, exactly the Global Constraints table. Values are `{"fd_year": int, "preseason_as_of": datetime, "final_venue_team": str | None}`.
  - Ingest also writes `data/processed/cl_{fd_year}_fd.json` and `cl_{fd_year}_teams.json` for 2024, 2025 and 2026. Keep the 2026 file names unchanged.
  - `build_season(..., season: str, final_venue_team: str | None)`: the season label and final venue become parameters (defaults keep 2026-27 behaviour).
  - `build_lambdas(model, team_ids, rating_sigma: float = 0.0)` adds `"eloCoef": model.coef_elo` and `"ratingSigma": rating_sigma`, and sets `"model"` to the actual model name.
  - `run_export(as_of, out, season="2026-27", model_name="elo-dc-v1")`. For `elo-dc-v2` it uses `run_elo_v2` and the alpha from `model_params.json`, and passes `rating_sigma` (null → 0.0).
  - CLI: `uclpred export --as-of <…|preseason|now> --out <dir> [--season 2024-25|2025-26|2026-27] [--model elo-dc-v1|elo-dc-v2]`. `--as-of preseason` takes `SEASONS[season]["preseason_as_of"]`.
  - Coefficients for 2024 and 2025: run `uclpred coefficients --season-year 2024` and `--season-year 2025` (network, cached). The export uses `season_year` = the start year.
- [ ] **Step 1: Write the failing tests:**
  - a past-season `build_season` with `season="2024-25"` and `final_venue_team="ger-bayern-munchen"` validates (144 fixtures, 4H/4A) and carries both values;
  - `build_lambdas` output has `eloCoef == model.coef_elo` and `ratingSigma == 0.0` by default;
  - `--as-of preseason` resolves per season.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Real exports.**
  1. Re-run `uv run uclpred ingest`. Raw data is cached; if a fresh football-data fetch is triggered and is slow, run it in the background.
  2. Run the two coefficient commands.
  3. Export `--season 2024-25 --as-of preseason` and `--season 2025-26 --as-of preseason`, each for both models, into `data/export/bt/<season>/<model>/`.
  All four must validate. md00 / live (2026-27) are not regenerated in this task.
- [ ] **Step 6: Commit:** `feat(pipeline): multi-season export with model switch and lambda metadata`

---

### Task 6: Rating uncertainty in the simulator

**Files:**
- Modify: `sim/src/types.ts`, `sim/src/simulate.ts`, `sim/src/cli.ts`
- Create: `sim/tests/uncertainty.test.ts`

**Interfaces:**
- Consumes: the `simulate(season, lambdas, opts)` flow; `samplePoisson`; `createRng`.
- Produces:
  - `Lambdas` gains `eloCoef?: number` and `ratingSigma?: number`.
  - `SimOptions` gains `ratingSigma?: number`. When given it overrides `lambdas.ratingSigma`; the effective value is `opts.ratingSigma ?? lambdas.ratingSigma ?? 0`.
  - A noisy sampler `NoisySampler` (implements `MatchSampler` from `tie.ts`):
    - built per run from the base `ScoreSampler`, `eloCoef` and a `Map<TeamId, number>` of noise draws;
    - `lambda(a, b, venue)` returns `[λa·exp(β(na−nb)/100), λb·exp(β(nb−na)/100)]`;
    - `sample` draws independent Poisson goals from those λ.
  - Noise draws: `n_t = σ·z` with `z` standard normal from Box–Muller on the run's seeded RNG, one per team per run.
  - With σ > 0 but `eloCoef` missing, throw a clear Error.
  - CLI flags `--sigma <number>` and `--out <file>` (write `chances.json` to this path instead of `<input>/chances.json`).
- [ ] **Step 1: Write the failing tests:**
  - `sigma0_identical_to_current`: an old-format `lambdas` (no new fields) and the same lambdas with `ratingSigma: 0, eloCoef: 0.16`, same seed, give deep-equal results;
  - `sigma_reduces_concentration`: on a synthetic 36-team season with a clear favourite, max `reach.winner` at σ = 100 is lower than at σ = 0 (same seed, 4,000 runs);
  - `noisy_played_fixtures_never_resampled`: with all 144 played and σ = 100, positions stay one-hot;
  - `deterministic_with_sigma`: same seed and σ give identical results;
  - `sigma_without_eloCoef_throws`.
- [ ] **Step 2: Run** `pnpm --filter @uclpred/sim test -- tests/uncertainty.test.ts`. Expected: FAIL.
- [ ] **Step 3: Implement.** The σ = 0 path must not touch the RNG differently from today, or the determinism comparison breaks.
- [ ] **Step 4: Run** the full sim suite and `tsc --noEmit`. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(sim): optional rating uncertainty with per-run Elo noise`

---

### Task 7: Tournament check on past seasons

**Files:**
- Create: `pipeline/src/uclpred/tournament_check.py`, `pipeline/tests/test_tournament_check.py`
- Modify: `pipeline/src/uclpred/cli.py`, `reports/calibration.md`, `data/reference/model_params.json`

**Interfaces:**
- Consumes: the Task 5 exports in `data/export/bt/<season>/<model>/`; the Task 6 sim CLI `--sigma` / `--out`; `processed/cl_{fd_year}_fd.json` and `cl_{fd_year}_teams.json`; `TeamResolver`.
- Produces:
  - `actual_outcomes(fd_matches: list[dict], resolver, team_country) -> dict[str, str]`, mapping team id → one of `out, po, r16, qf, sf, final, winner`. It is derived from football-data `stage` membership:
    - `PLAYOFFS` participants are `po` unless they also appear in `LAST_16`;
    - top-8 teams are `LAST_16` participants absent from `PLAYOFFS`;
    - the highest stage reached wins;
    - the winner is the `FINAL` match's `score.winner` side.
  - `stage_distribution(chances_team: dict) -> dict[str, float]`, the probability of finishing exactly at each stage:
    - `out` = `out`
    - `po` = `reach.po − (reach.r16 − top8)`
    - `r16` = `reach.r16 − reach.qf`
    - `qf` = `reach.qf − reach.sf`
    - `sf` = `reach.sf − reach.final`
    - `final` = `reach.final − reach.winner`
    - `winner` = `reach.winner`

    These sum to `out + reach.po + top8 = 1`.
  - `score_tournament(chances: dict, actual: dict[str,str]) -> dict` with keys:
    - `stage_log_loss`: mean −log P(actual stage), with ε = 1e-6;
    - `brier_top8`, `brier_top24`;
    - `max_title_share`.
  - CLI `uclpred tournament-check [--runs 50000]`: for each season in {2024-25, 2025-26} × model in {v1, v2} × σ in the grid, run `pnpm --filter @uclpred/sim cli -- --input data/export/bt/<season>/<model> --sigma <σ> --out data/export/bt/<season>/<model>/chances_s<σ>.json --runs <runs> --seed 1` via `subprocess` with cwd = repo root, then score.
    - Choose σ for v2 by the lowest mean `stage_log_loss` over both seasons; if all are within 0.01, pick 70.
    - Write `rating_sigma` into `model_params.json`.
    - Append the "Tournament check" table and the chosen σ to `reports/calibration.md`.
- [ ] **Step 1: Write the failing tests:**
  - `actual_outcomes` on a synthetic fd list (2 PLAYOFFS ties, LAST_16 … FINAL) gives the right labels, including a top-8 team that lost in the R16 → `r16`;
  - `stage_distribution` sums to 1 and matches the hand values;
  - `score_tournament` on a 3-team toy gives the hand-computed log loss and Brier scores.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Real run** `uv run uclpred tournament-check`. That is 16 simulations of 50k runs, about 1–2 s each. Paste the table into the task report.
- [ ] **Step 6: Commit:** `feat(pipeline): past-season tournament check and rating-sigma choice`

---

### Task 8: Gate verdict and (if passing) switch to `elo-dc-v2`

**Files:**
- Modify: `reports/calibration.md`; if the gate passes, also `pipeline/src/uclpred/config.py` (`MODEL_NAME`), `reports/m1-first-run.md`, `.claude/skills/modeling-match-outcomes/SKILL.md`, `.claude/skills/backtesting-predictions/SKILL.md`, `README.md`

**Interfaces:**
- Consumes: the numbers in `reports/calibration.md` and `model_params.json`.
- Produces: a "Gate verdict" section listing criteria 1–3 with PASS/FAIL and the numbers. Criterion 4 is marked "pending user review".

- [ ] **Step 1: Write** the gate verdict section from the recorded numbers, quoting each threshold from Global Constraints.
- [ ] **Step 2: If any of criteria 1–3 fails:** stop. Commit the report with `docs: calibration gate verdict (fail)`, then report BLOCKED with the failing criteria. Do not switch models.
- [ ] **Step 3: If 1–3 pass:**
  1. Set `MODEL_NAME = "elo-dc-v2"` and make the CLI's `--model` default follow `MODEL_NAME`.
  2. Regenerate: `uv run uclpred export --as-of preseason --out data/export/md00` and `--as-of now --out data/export/live` (both v2), then `pnpm --filter @uclpred/sim cli -- --input data/export/md00` and `data/export/live`.
  3. Rewrite `reports/m1-first-run.md` with the new tables and a before/after comparison of the top-10 (v1 vs v2). Keep the caveat, now worded "pending user review (gate criterion 4)".
  4. Update the modeling skill: the `elo-dc-v2` description, chosen params and σ. Update the backtesting skill: the harness commands, the gate and the latest numbers. Keep each ≲ 550 words.
  5. Update the README commands (`backtest`, `tournament-check`, `--model`, `--season`).
- [ ] **Step 4: Full verification:**
  - `cd pipeline && uv run ruff check . && uv run pytest && uv run pytest -m data`
  - `pnpm --filter @uclpred/sim test`
  - `pnpm --filter @uclpred/sim exec tsc --noEmit`
  - `git grep -n "/Users/" -- ':!*.lock'` must be empty.
- [ ] **Step 5: Commit:** `feat: switch default model to elo-dc-v2 after calibration gate` (or the fail-path commit from Step 2).
