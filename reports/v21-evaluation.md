# v2.1 evaluation

## Verdict

G1–G4: PASS — elo-dc-v2.1 is the default model

G4 was decided by the user after run 1. reports/v21-evaluation.json is run 1's machine output (G4 pending at run time) and is unchanged.

## Settings

Pre-registered in commit `381a8a8` (§2); read from `model_params.json`, not tuned.

| Setting | Value |
|---|---|
| Model | `elo-dc-v2.1` vs `elo-dc-v1` (`run_elo`, alpha 0.005) |
| Elo | `run_elo_v2` k=24, k_euro=2.0, g=0.9, g_pseudo=0.0, home_adv=60 |
| GLM | `fit_baseline` alpha=0.005; xi=0.0019, window_days=1460, euro_weight=2.0 |
| Rating uncertainty | sigma = 0 |
| Bootstrap | 1,000 match resamples, seed 1, 95% percentile CI |

## Gates

| Gate | Value | Threshold | Result |
|---|---|---|---|
| G1 | -0.021006501 (n=284; v1 -0.151877701) | \|gap(v2.1)\| ≤ 0.03 | PASS |
| G2 | +0.002810009 (ΔRPS CI upper) | ≤ +0.003 | PASS |
| G3 | +0.003210197 (ΔRPS CI upper) | ≤ +0.006 | PASS |
| G4 | user approved 2026-11-10 | user says yes | PASS |

## Diagnostics

### Deltas

- G2 (uefa.*, 2022-23 … 2025-26, n=2390): RPS v1 0.2089, v2.1 0.2096; ΔRPS +0.000629726 [-0.001484436, +0.002810009]
- G3 (all competitions, holdout, n=589): RPS v1 0.1983, v2.1 0.1996; ΔRPS +0.001271342 [-0.000763736, +0.003210197]

### Home-win calibration

| Window | Model | Mean p_home | Observed | Diff |
|---|---|---|---|---|
| uefa.* 2022-26 | v1 | 0.4425 | 0.4845 | -0.0420 |
| uefa.* 2022-26 | v2.1 | 0.4437 | 0.4845 | -0.0408 |
| holdout (all competitions) | v1 | 0.4423 | 0.4601 | -0.0178 |
| holdout (all competitions) | v2.1 | 0.4434 | 0.4601 | -0.0167 |

### G3 by competition

| Competition | n | RPS v1 | RPS v2.1 |
|---|---|---|---|
| it.1 | 82 | 0.1980 | 0.2004 |
| es.1 | 80 | 0.1727 | 0.1760 |
| uefa.cl | 72 | 0.1855 | 0.1858 |
| en.1 | 70 | 0.2157 | 0.2148 |
| nl.1 | 67 | 0.2167 | 0.2167 |
| de.1 | 63 | 0.1980 | 0.1981 |
| fr.1 | 63 | 0.1936 | 0.1974 |
| pt.1 | 57 | 0.2041 | 0.2046 |
| en.2 | 35 | 0.2134 | 0.2149 |

### Tournament check (reported, not gating; sigma 0, 50,000 runs, seed 1)

| Season | Model | stage_log_loss |
|---|---|---|
| 2024-25 | elo-dc-v1 | 1.3935 |
| 2024-25 | elo-dc-v2.1 | 1.5059 |
| 2025-26 | elo-dc-v1 | 1.3230 |
| 2025-26 | elo-dc-v2.1 | 1.3321 |
| mean | elo-dc-v1 | 1.3582 |
| mean | elo-dc-v2.1 | 1.4190 |

## G4 review

Top 12 teams by v2.1 Winner %; v1 = `elo-dc-v1`, v2.1 = `elo-dc-v2.1`; both on the same corrected data, 50,000 runs, seed 1, sigma 0. Top 8 / Top 24 / Win in %.

### Pre-season (matchday 0)

| Team | v1 Top 8 % | v2.1 Top 8 % | v1 Top 24 % | v2.1 Top 24 % | v1 Win % | v2.1 Win % |
|---|---|---|---|---|---|---|
| Bayern | 86.9 | 79.1 | 99.8 | 99.4 | 29.4 | 24.2 |
| Arsenal | 78.5 | 66.7 | 99.4 | 98.6 | 23.9 | 17.0 |
| PSG | 54.5 | 69.5 | 96.5 | 98.6 | 8.5 | 16.7 |
| Barça | 58.8 | 64.6 | 97.0 | 98.2 | 9.9 | 12.3 |
| Real Madrid | 37.9 | 56.1 | 92.0 | 96.7 | 3.3 | 6.1 |
| Man City | 31.8 | 32.6 | 88.8 | 89.5 | 3.6 | 4.6 |
| Sporting CP | 36.9 | 29.0 | 91.1 | 87.5 | 3.4 | 2.4 |
| Inter | 47.3 | 39.9 | 94.6 | 92.3 | 3.8 | 2.2 |
| Dortmund | 37.1 | 38.8 | 91.7 | 92.4 | 1.8 | 2.2 |
| Lille | 7.0 | 23.4 | 61.3 | 84.7 | 0.2 | 2.2 |
| RC Lens | 7.9 | 24.9 | 58.9 | 83.1 | 0.1 | 1.5 |
| Bodø/Glimt | 14.3 | 20.5 | 73.7 | 80.7 | 0.4 | 1.2 |

Teams with Top 8 % change >= 10 points (Pre-season (matchday 0)): Real Madrid (+18.2), RC Lens (+17.0), Lille (+16.4), PSG (+15.0), Fenerbahçe (-15.0), PSV (-11.9), Arsenal (-11.8)

### Live (now)

| Team | v1 Top 8 % | v2.1 Top 8 % | v1 Top 24 % | v2.1 Top 24 % | v1 Win % | v2.1 Win % |
|---|---|---|---|---|---|---|
| Bayern | 87.2 | 82.6 | 100.0 | 100.0 | 22.8 | 21.0 |
| Barça | 79.6 | 82.5 | 100.0 | 100.0 | 13.6 | 18.0 |
| Arsenal | 91.8 | 88.2 | 100.0 | 100.0 | 20.4 | 16.2 |
| PSG | 96.4 | 93.4 | 100.0 | 100.0 | 19.0 | 12.9 |
| Real Madrid | 94.5 | 96.7 | 100.0 | 100.0 | 7.7 | 10.7 |
| Como 1907 | 51.0 | 53.6 | 99.9 | 99.9 | 3.9 | 4.8 |
| Inter | 24.1 | 28.0 | 97.9 | 98.4 | 2.2 | 3.4 |
| Man City | 50.6 | 48.5 | 99.8 | 99.7 | 2.4 | 2.8 |
| Dortmund | 30.3 | 33.5 | 99.3 | 99.4 | 1.1 | 1.6 |
| Atleti | 2.7 | 4.9 | 76.1 | 84.3 | 0.4 | 1.4 |
| Liverpool | 39.5 | 37.7 | 99.6 | 99.5 | 1.1 | 1.3 |
| Roma | 1.8 | 3.1 | 72.1 | 78.0 | 0.6 | 1.3 |

Teams with Top 8 % change >= 10 points (Live (now)): none

## G4 context (post-hoc, non-gating)

Diagnostics computed after run 1 for the user's G4 decision; they do not change any gate result.

Reproduced read-only from the committed code and data (no run, no files written). The G1/G2/G3 values reproduce the record (G1 exactly; G2/G3 bounds to within 4e-14, floating-point noise).

### 1. Margins

| Gate | Mean ΔRPS (v2.1 − v1) | 95% CI | Threshold on upper bound |
|---|---|---|---|
| G2 (n=2390) | +0.000630 | [−0.001484, +0.002810] | +0.003 (margin 0.00019) |
| G3 (n=589) | +0.001271 | [−0.000764, +0.003210] | +0.006 (margin 0.00279) |

- G2 upper-bound sensitivity to the bootstrap seed (seeds 1–200, 1,000 resamples each): min +0.00254, median +0.00276, max +0.00305; 1 of 200 seeds (0.5%) exceeds +0.003. The recorded seed-1 value (+0.00281) is close to the median. G3 over the same seeds: median +0.00328, max +0.00355 (none above +0.006).
- Clustered bootstrap (1,000 resamples, seed 1), G2: by tie/team pair (1,445 clusters) CI [−0.00163, +0.00289]; by month (39 clusters) CI [−0.00186, +0.00320], so the month-clustered upper bound is above +0.003. G3: by pair (589 clusters) [−0.00077, +0.00323]; by month (3 clusters, not meaningful) [+0.00024, +0.00435].

### 2. Bias in final predictions

Mean (observed − expected) score of mid-league vs Big-5 clubs, 2022-26, using the final GLM match probabilities (not the Elo input that G1 uses), same 284 matches as G1: v1 −0.1386; v2.1 −0.0775. (G1's Elo-input gap: v1 −0.1519; v2.1 −0.0210.)

### 3. League levels under v2.1

| League | 2026-09-07 (md00 cut-off) | 2026-11-09 |
|---|---|---|
| en.1 | 1637 | 1639 |
| es.1 | 1651 | 1661 |
| de.1 | 1619 | 1609 |
| it.1 | 1492 | 1561 |
| fr.1 | 1691 | 1581 |
| nl.1 | 1411 | 1362 |
| pt.1 | 1448 | 1435 |

Ligue 1 rose from 1456 (2023-07-01) to 1691 (2026-09-07), +235. European-result contributions over 2023-07 to 2026-09-07 (0.9 × Δ, summed): +234 in total (+222 vs real clubs, +13 vs pseudo opponents). By club: PSG +238, Lyon +113, Lille +107, Brest +65, Lens −60, Nice −248. At md00, Lille's rating is 1699 (v1) vs 1892 (v2.1), Lens 1676 vs 1874, PSG 1885 vs 2025 (see the Top 8 table above for the resulting probabilities).

### 4. Matchdays 1–4 check

Each model's md00 (pre-season) predictions scored on the 72 played 2026-27 CL matches: RPS v1 0.1837, v2.1 0.1841; Δ +0.0004 ± 0.0060 (SE); log-loss 0.8270 vs 0.8290. Largest per-team RPS losses under v2.1 (sum of per-match RPS differences): RC Lens +0.339, Lille +0.288, Como +0.226, Sporting CP +0.175, Galatasaray +0.153, Liverpool +0.116. Largest gains: Real Madrid −0.198, Aston Villa −0.142, Porto −0.129, Man City −0.121, Roma −0.121, Slavia Praha −0.101. (Lens lost 1–9 to Como; Lille 2–4 to Galatasaray.)

### 5. 2024-25 tournament check: main contributors

Per-team stage log-loss, v2.1 − v1 (2024-25 mean +0.1124, n=36; 2025-26 mean +0.0092). Largest increases in 2024-25: Aston Villa (QF) +1.651, Girona (out) +0.981, Arsenal (SF) +0.819, Bologna (out) +0.692, Liverpool (R16) +0.585. Biggest offset: Man City (play-off) −1.733 (next: Inter −0.442).

### 6. Plain-language reading

v2.1 shifts a whole league's level by 0.9 × Δ for each European result between clubs of different leagues, with no decay, so every club inherits its compatriots' European record: Lille and Lens rose because PSG and Lyon did well in Europe, even though Lille/Lens themselves did not (Lens −60). This is a modelling consequence of the pre-registered design, not a bug. The effect is a pre-season prior: on live tables the two models converge, and no team moves 10 points or more on Top 8 % (see the Live table above).

## Run log

- 2026-11-10T11:52:36Z af0382a run 1 started
- 2026-11-10T11:52:40Z run 1 result: G1 -0.021006501 PASS; G2 +0.002810009 PASS; G3 +0.003210197 PASS; G4 pending user review; verdict: G1–G3: PASS — pending user review (G4)
