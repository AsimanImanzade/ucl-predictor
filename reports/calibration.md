# Calibration report

Elo v2 parameter search and v1 vs v2 backtest, generated 2026-11-10 by `uv run uclpred backtest`. Parameters chosen on tuning seasons 2019-20, 2020-21, 2021-22; compared on report seasons 2022-23, 2023-24, 2024-25, 2025-26.

## Grid (top 10)

Tuning-season mean RPS, 81 grid points, sorted by RPS.

| k | k_euro | g | alpha | rps | log_loss | brier | league_gap |
|---|---|---|---|---|---|---|---|
| 24.0 | 1.0 | 0.9 | 0.0005 | 0.1995 | 0.9592 | 0.5663 | -0.061 |
| 24.0 | 1.5 | 0.9 | 0.0005 | 0.1995 | 0.9592 | 0.5664 | -0.048 |
| 20.0 | 1.0 | 0.9 | 0.0005 | 0.1995 | 0.9594 | 0.5663 | -0.065 |
| 24.0 | 1.0 | 0.7 | 0.0005 | 0.1996 | 0.9594 | 0.5664 | -0.067 |
| 24.0 | 1.5 | 0.7 | 0.0005 | 0.1996 | 0.9593 | 0.5664 | -0.052 |
| 20.0 | 1.5 | 0.7 | 0.0005 | 0.1997 | 0.9597 | 0.5666 | -0.057 |
| 16.0 | 1.0 | 0.9 | 0.0005 | 0.1997 | 0.9600 | 0.5666 | -0.071 |
| 24.0 | 1.5 | 0.5 | 0.0005 | 0.1997 | 0.9598 | 0.5667 | -0.059 |
| 20.0 | 1.5 | 0.9 | 0.0005 | 0.1997 | 0.9599 | 0.5667 | -0.052 |
| 20.0 | 1.0 | 0.7 | 0.0005 | 0.1997 | 0.9600 | 0.5667 | -0.072 |

## Chosen parameters

| k | k_euro | g | home_adv | alpha |
|---|---|---|---|---|
| 24.0 | 2.0 | 0.9 | 60.0 | 0.0005 |

Selection: lowest tuning-season RPS; ties within 0.0005 go to the smaller |league gap|.

## Report seasons: v1 vs v2

| model | rps | log_loss | brier | n |
|---|---|---|---|---|
| elo-dc-v1 (alpha 0.005) | 0.2089 | 0.9801 | 0.5833 | 2390 |
| elo-dc-v2 (chosen) | 0.2107 | 0.9885 | 0.5871 | 2390 |

Delta RPS (v2 - v1): +0.0018, 95% CI [-0.0011, +0.0046] (1,000 bootstrap resamples of match ids, seed 1).

## Calibration (v2)

Home-win probability bins on report seasons.

| bin_lo | bin_hi | n | mean_pred | observed |
|---|---|---|---|---|
| 0.0 | 0.1 | 42 | 0.0687 | 0.0714 |
| 0.1 | 0.2 | 166 | 0.1554 | 0.2530 |
| 0.2 | 0.3 | 339 | 0.2546 | 0.2802 |
| 0.3 | 0.4 | 437 | 0.3520 | 0.4279 |
| 0.4 | 0.5 | 561 | 0.4458 | 0.5027 |
| 0.5 | 0.6 | 394 | 0.5471 | 0.5990 |
| 0.6 | 0.7 | 232 | 0.6464 | 0.6379 |
| 0.7 | 0.8 | 139 | 0.7467 | 0.7050 |
| 0.8 | 0.9 | 68 | 0.8393 | 0.8382 |
| 0.9 | 1.0 | 12 | 0.9300 | 0.8333 |

## League gap

Mean (actual - expected Elo score) for mid-league clubs against Big-5 clubs in European matches.

| model | scope | gap | n |
|---|---|---|---|
| elo-dc-v1 | 2019-20 onwards | -0.161 | 419 |
| elo-dc-v2 | 2019-20 onwards | -0.040 | 419 |
| elo-dc-v1 | report seasons | -0.152 | 268 |
| elo-dc-v2 | report seasons | -0.023 | 268 |
