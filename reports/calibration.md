# Calibration report

Elo v2 parameter search and v1 vs v2 backtest, generated 2026-11-10 by `uv run uclpred backtest`. Parameters chosen on tuning seasons 2019-20, 2020-21, 2021-22; compared on report seasons 2022-23, 2023-24, 2024-25, 2025-26.

## Gate verdict

Pre-registered gate (thresholds from Global Constraints), evaluated on the recorded numbers above.

| # | criterion (threshold) | v1 | v2 | result |
|---|---|---|---|---|
| 1 | League gap, gate scope 2019-20 ... 2025-26 (n=416): \|league gap v2\| <= 0.03 | -0.160 | -0.041 | **FAIL** |
| 2 | Report seasons 2022-23 ... 2025-26 (n=2390): upper bound of 95% CI of delta RPS (v2 - v1) <= +0.001 | RPS 0.2086 | RPS 0.2105; delta +0.0019, CI [-0.0011, +0.0047] | **FAIL** |
| 3 | Mean tournament log loss over 2024-25 and 2025-26: v2 at chosen sigma <= v1 at sigma = 0 | 1.3401 (sigma 0) | 1.3694 (sigma 70); +0.0293 | **FAIL** |
| 4 | User review of the md00 table | - | - | pending user review (not reached; no switch happened) |

Gate: FAIL (criteria 1, 2, 3). Default model stays elo-dc-v1; no switch performed. Decision pending with the user.

### Evidence for the decision

Diagnostics outside the pre-registered gate; they do not change the verdict.

- At equal regularisation (alpha 0.005) v2's Elo beats v1 on report seasons: delta -0.0012, CI [-0.0037, +0.0014] (Sensitivity section). The criterion 2 failure comes from the tuned alpha 0.0005, which was tuned on COVID-affected 2019-20/2020-21 and does not transfer.
- Closing the league gap to the 0.03 band needs extreme settings (k=32, k_euro=3.0, g=1.0: gap -0.029 in the Sensitivity table) which cost accuracy (delta +0.0027, CI [-0.0005, +0.0059]).
- Criterion 3's failure is small relative to its noise: a team-season bootstrap gives CI [-0.044, +0.103]. Aston Villa's 2024-25 quarter-final run (v1 P 0.077 vs v2 0.026) is about half the gap; 2025-26 is nearly tied (1.328 vs 1.321).
- Rating uncertainty barely moves title concentration under v2 because v2's eloCoef (about 0.093 per 100 Elo) is about half of v1's (0.162): noise acts only on the Elo term, not on team attack/defence.
- Hazard: re-running `uclpred backtest` rewrites `rating_sigma` to null in model_params.json (backtest.py:255); re-run `uclpred tournament-check` afterwards to restore it.

## Tournament check

Past seasons 2024-25, 2025-26, preseason exports, 50,000 runs, seed 1. stage_log_loss is the mean over the 36 teams of -log P(actual stage), floored at 1e-6; brier_top8 scores the direct top-8 flag (played the Round of 16 without the play-offs); brier_top24 scores 'not out'; max_title_share is the largest title probability.

| season | model | sigma | stage_log_loss | brier_top8 | brier_top24 | max_title_share |
|---|---|---|---|---|---|---|
| 2024-25 | elo-dc-v1 | 0 | 1.3590 | 0.1687 | 0.1277 | 0.2899 |
| 2024-25 | elo-dc-v1 | 40 | 1.3578 | 0.1678 | 0.1283 | 0.2785 |
| 2024-25 | elo-dc-v1 | 70 | 1.3601 | 0.1661 | 0.1297 | 0.2524 |
| 2024-25 | elo-dc-v1 | 100 | 1.3652 | 0.1634 | 0.1315 | 0.2213 |
| 2024-25 | elo-dc-v2 | 0 | 1.4150 | 0.1756 | 0.1532 | 0.1696 |
| 2024-25 | elo-dc-v2 | 40 | 1.4143 | 0.1756 | 0.1530 | 0.1658 |
| 2024-25 | elo-dc-v2 | 70 | 1.4107 | 0.1745 | 0.1529 | 0.1586 |
| 2024-25 | elo-dc-v2 | 100 | 1.4107 | 0.1735 | 0.1528 | 0.1537 |
| 2025-26 | elo-dc-v1 | 0 | 1.3212 | 0.1157 | 0.1530 | 0.1745 |
| 2025-26 | elo-dc-v1 | 40 | 1.3256 | 0.1170 | 0.1531 | 0.1649 |
| 2025-26 | elo-dc-v1 | 70 | 1.3377 | 0.1189 | 0.1542 | 0.1508 |
| 2025-26 | elo-dc-v1 | 100 | 1.3540 | 0.1208 | 0.1571 | 0.1340 |
| 2025-26 | elo-dc-v2 | 0 | 1.3286 | 0.0796 | 0.1568 | 0.2840 |
| 2025-26 | elo-dc-v2 | 40 | 1.3271 | 0.0800 | 0.1565 | 0.2790 |
| 2025-26 | elo-dc-v2 | 70 | 1.3281 | 0.0807 | 0.1570 | 0.2702 |
| 2025-26 | elo-dc-v2 | 100 | 1.3296 | 0.0815 | 0.1577 | 0.2597 |
| mean | elo-dc-v1 | 0 | 1.3401 | 0.1422 | 0.1403 | 0.2322 |
| mean | elo-dc-v1 | 40 | 1.3417 | 0.1424 | 0.1407 | 0.2217 |
| mean | elo-dc-v1 | 70 | 1.3489 | 0.1425 | 0.1420 | 0.2016 |
| mean | elo-dc-v1 | 100 | 1.3596 | 0.1421 | 0.1443 | 0.1776 |
| mean | elo-dc-v2 | 0 | 1.3718 | 0.1276 | 0.1550 | 0.2268 |
| mean | elo-dc-v2 | 40 | 1.3707 | 0.1278 | 0.1547 | 0.2224 |
| mean | elo-dc-v2 | 70 | 1.3694 | 0.1276 | 0.1549 | 0.2144 |
| mean | elo-dc-v2 | 100 | 1.3701 | 0.1275 | 0.1552 | 0.2067 |

Chosen rating_sigma for elo-dc-v2: **70**. Rule: lowest mean stage_log_loss over both seasons among [0, 40, 70, 100]; if the max-min spread of the four means is at most 0.01, choose 70. Observed spread 0.0024 (0: 1.3718, 40: 1.3707, 70: 1.3694, 100: 1.3701).

Gate 3 comparison (mean stage_log_loss over both seasons): v2 at sigma 70 = 1.3694, v1 at sigma 0 = 1.3401; v2 <= v1: **FAIL**.

## Grid (top 10)

Tuning-season mean RPS, 81 grid points, sorted by RPS. Full grid: `reports/backtest_grid.csv`.

| k | k_euro | g | alpha | rps | log_loss | brier | league_gap |
|---|---|---|---|---|---|---|---|
| 24.0 | 1.0 | 0.9 | 0.0005 | 0.1995 | 0.9592 | 0.5663 | -0.061 |
| 24.0 | 1.5 | 0.9 | 0.0005 | 0.1995 | 0.9592 | 0.5664 | -0.049 |
| 20.0 | 1.0 | 0.9 | 0.0005 | 0.1995 | 0.9594 | 0.5663 | -0.066 |
| 24.0 | 1.0 | 0.7 | 0.0005 | 0.1996 | 0.9594 | 0.5664 | -0.067 |
| 24.0 | 1.5 | 0.7 | 0.0005 | 0.1996 | 0.9593 | 0.5664 | -0.052 |
| 20.0 | 1.5 | 0.7 | 0.0005 | 0.1997 | 0.9597 | 0.5666 | -0.057 |
| 16.0 | 1.0 | 0.9 | 0.0005 | 0.1997 | 0.9600 | 0.5666 | -0.070 |
| 24.0 | 1.5 | 0.5 | 0.0005 | 0.1997 | 0.9598 | 0.5667 | -0.059 |
| 20.0 | 1.5 | 0.9 | 0.0005 | 0.1997 | 0.9599 | 0.5667 | -0.052 |
| 20.0 | 1.0 | 0.7 | 0.0005 | 0.1997 | 0.9600 | 0.5667 | -0.072 |

## Chosen parameters

| k | k_euro | g | home_adv | alpha | rps | log_loss | brier | league_gap |
|---|---|---|---|---|---|---|---|---|
| 24.0 | 2.0 | 0.9 | 60.0 | 0.0005 | 0.1998 | 0.9600 | 0.5670 | -0.041 |

Selection: lowest tuning-season RPS; ties within 0.0005 go to the smaller |league gap|. The gap is the Global-Constraints scope (2019-20 ... 2025-26). A tuning-seasons-only gap (2019-20 ... 2021-22) selects the same Elo set (chosen set's tuning-only gap -0.070).

### Candidates within 0.0005 of best (26)

| k | k_euro | g | alpha | rps | log_loss | brier | league_gap |
|---|---|---|---|---|---|---|---|
| 24.0 | 1.0 | 0.9 | 0.0005 | 0.1995 | 0.9592 | 0.5663 | -0.061 |
| 24.0 | 1.5 | 0.9 | 0.0005 | 0.1995 | 0.9592 | 0.5664 | -0.049 |
| 20.0 | 1.0 | 0.9 | 0.0005 | 0.1995 | 0.9594 | 0.5663 | -0.066 |
| 24.0 | 1.0 | 0.7 | 0.0005 | 0.1996 | 0.9594 | 0.5664 | -0.067 |
| 24.0 | 1.5 | 0.7 | 0.0005 | 0.1996 | 0.9593 | 0.5664 | -0.052 |
| 20.0 | 1.5 | 0.7 | 0.0005 | 0.1997 | 0.9597 | 0.5666 | -0.057 |
| 16.0 | 1.0 | 0.9 | 0.0005 | 0.1997 | 0.9600 | 0.5666 | -0.070 |
| 24.0 | 1.5 | 0.5 | 0.0005 | 0.1997 | 0.9598 | 0.5667 | -0.059 |
| 20.0 | 1.5 | 0.9 | 0.0005 | 0.1997 | 0.9599 | 0.5667 | -0.052 |
| 20.0 | 1.0 | 0.7 | 0.0005 | 0.1997 | 0.9600 | 0.5667 | -0.072 |
| 16.0 | 1.5 | 0.9 | 0.0005 | 0.1997 | 0.9600 | 0.5667 | -0.056 |
| 16.0 | 1.5 | 0.7 | 0.0005 | 0.1997 | 0.9601 | 0.5667 | -0.061 |
| 20.0 | 2.0 | 0.7 | 0.0005 | 0.1998 | 0.9600 | 0.5668 | -0.047 |
| 24.0 | 2.0 | 0.7 | 0.0005 | 0.1998 | 0.9598 | 0.5669 | -0.044 |
| 20.0 | 2.0 | 0.9 | 0.0005 | 0.1998 | 0.9600 | 0.5669 | -0.044 |
| 20.0 | 1.5 | 0.5 | 0.0005 | 0.1998 | 0.9602 | 0.5669 | -0.064 |
| 24.0 | 1.0 | 0.5 | 0.0005 | 0.1998 | 0.9602 | 0.5669 | -0.075 |
| 16.0 | 2.0 | 0.9 | 0.0005 | 0.1998 | 0.9602 | 0.5669 | -0.048 |
| 16.0 | 2.0 | 0.7 | 0.0005 | 0.1998 | 0.9603 | 0.5670 | -0.052 |
| 24.0 | 2.0 | 0.5 | 0.0005 | 0.1998 | 0.9601 | 0.5670 | -0.049 |
| 24.0 | 2.0 | 0.9 | 0.0005 | 0.1998 | 0.9600 | 0.5670 | -0.041 |
| 20.0 | 2.0 | 0.5 | 0.0005 | 0.1999 | 0.9603 | 0.5671 | -0.053 |
| 16.0 | 1.0 | 0.7 | 0.0005 | 0.1999 | 0.9606 | 0.5671 | -0.077 |
| 16.0 | 1.5 | 0.5 | 0.0005 | 0.1999 | 0.9606 | 0.5671 | -0.069 |
| 20.0 | 1.0 | 0.5 | 0.0005 | 0.1999 | 0.9606 | 0.5671 | -0.081 |
| 16.0 | 2.0 | 0.5 | 0.0005 | 0.2000 | 0.9608 | 0.5672 | -0.058 |

## Report seasons: v1 vs v2

| model | rps | log_loss | brier | n |
|---|---|---|---|---|
| elo-dc-v1 (alpha 0.005) | 0.2086 | 0.9794 | 0.5827 | 2390 |
| elo-dc-v2 (chosen) | 0.2105 | 0.9880 | 0.5866 | 2390 |

Delta RPS (v2 - v1): +0.0019, 95% CI [-0.0011, +0.0047] (1,000 bootstrap resamples of match ids, seed 1).

## Sensitivity (outside the pre-registered selection)

Diagnostic evaluations on the report seasons for the gate decision, not a re-selection. All rows use identical matches; delta is vs v1 @ alpha 0.005 (95% bootstrap CI); gate_gap uses the Gate 1 scope (2019-20 ... 2025-26).

| variant | rps | log_loss | brier | delta_rps_vs_v1 | ci_lo | ci_hi | gate_gap |
|---|---|---|---|---|---|---|---|
| v1 @ alpha 0.0005 | 0.2101 | 0.9862 | 0.5861 | 0.0014 | -0.0008 | 0.0034 | -0.160 |
| v2 chosen Elo @ alpha 0.005 | 0.2074 | 0.9764 | 0.5794 | -0.0012 | -0.0037 | 0.0014 | -0.041 |
| v2 corner k=32 k_euro=3.0 g=1.0 @ alpha 0.005 | 0.2113 | 0.9887 | 0.5874 | 0.0027 | -0.0005 | 0.0059 | -0.029 |

## Calibration (v2)

Home-win probability bins on report seasons.

| bin_lo | bin_hi | n | mean_pred | observed |
|---|---|---|---|---|
| 0.0 | 0.1 | 40 | 0.0681 | 0.0750 |
| 0.1 | 0.2 | 165 | 0.1554 | 0.2485 |
| 0.2 | 0.3 | 342 | 0.2547 | 0.2807 |
| 0.3 | 0.4 | 436 | 0.3521 | 0.4289 |
| 0.4 | 0.5 | 562 | 0.4458 | 0.5000 |
| 0.5 | 0.6 | 393 | 0.5468 | 0.6056 |
| 0.6 | 0.7 | 235 | 0.6467 | 0.6340 |
| 0.7 | 0.8 | 139 | 0.7466 | 0.7050 |
| 0.8 | 0.9 | 66 | 0.8376 | 0.8333 |
| 0.9 | 1.0 | 12 | 0.9298 | 0.8333 |

## League gap

Mean (actual - expected Elo score) for mid-league clubs against Big-5 clubs in European matches, capped at season 2025-26.

| model | scope | gap | n |
|---|---|---|---|
| elo-dc-v1 | Gate 1 scope: 2019-20 ... 2025-26 | -0.160 | 416 |
| elo-dc-v2 | Gate 1 scope: 2019-20 ... 2025-26 | -0.041 | 416 |
| elo-dc-v1 | Report seasons only: 2022-23 ... 2025-26 | -0.150 | 265 |
| elo-dc-v2 | Report seasons only: 2022-23 ... 2025-26 | -0.024 | 265 |
