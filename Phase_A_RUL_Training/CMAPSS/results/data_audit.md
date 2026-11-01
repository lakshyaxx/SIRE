# C-MAPSS data audit

Audit date: 2026-11-01. Source files in `CMAPSS/data/` were parsed with whitespace separation, no header, and empty trailing columns removed.

Near-constant definition: at least 99.9% of the training rows share one exact sensor value. Constant sensors are exact zero-variance sensors.
Operating-condition clusters use StandardScaler and KMeans (`k=6`, `n_init=10`, seed 42), both fitted on training operating settings only; the fitted objects label test settings for audit counts.

## Subset summary

| Dataset | Train shape | Test shape | Train engines | Test engines | Train length min / median / max | Test length min / median / max | Official RUL rows | Expected engines (train/test) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FD001 | 20631 x 26 | 13096 x 26 | 100 | 100 | 128 / 199.0 / 362 | 31 / 133.5 / 303 | 100 (match) | 100/100 |
| FD002 | 53759 x 26 | 33991 x 26 | 260 | 259 | 128 / 199.0 / 378 | 21 / 132.0 / 367 | 259 (match) | 260/259 |
| FD003 | 24720 x 26 | 16596 x 26 | 100 | 100 | 145 / 220.5 / 525 | 38 / 148.0 / 475 | 100 (match) | 100/100 |
| FD004 | 61249 x 26 | 41214 x 26 | 249 | 248 | 128 / 234.0 / 543 | 19 / 153.5 / 486 | 248 (match) | 248/249 |

### FD001 details

- Operating conditions expected: 1; distinct training setting triplets rounded to 4 decimals: 1423.
- Columns: unit, cycle, op1, op2, op3, s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12, s13, s14, s15, s16, s17, s18, s19, s20, s21. Training dtypes: float64=22, int64=4; test dtypes: float64=22, int64=4.
- Missing values: train=0, test=0, official RUL=0.
- Exact constant training sensors: s1, s5, s10, s16, s18, s19.
- Near-constant training sensors (modal share >= 99.9%): s1 (100.0000% modal value), s5 (100.0000% modal value), s10 (100.0000% modal value), s16 (100.0000% modal value), s18 (100.0000% modal value), s19 (100.0000% modal value).
- Shortest test engines by cycle count: 1 (31 cycles), 85 (34 cycles), 39 (37 cycles), 22 (39 cycles), 14 (46 cycles), 25 (48 cycles), 2 (49 cycles), 33 (50 cycles), 69 (54 cycles), 44 (54 cycles).
- Training raw RUL distribution (cycles): min=0, median=103.0, max=361; clipped-at-125 median=103.0.
- Official test RUL distribution (cycles): min=7, median=86.0, max=145; test engine ordering check=unit ids 1..N.
- Operating-setting cluster row counts: not applicable (single operating condition).

### FD002 details

- Operating conditions expected: 6; distinct training setting triplets rounded to 4 decimals: 9824.
- Columns: unit, cycle, op1, op2, op3, s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12, s13, s14, s15, s16, s17, s18, s19, s20, s21. Training dtypes: float64=22, int64=4; test dtypes: float64=22, int64=4.
- Missing values: train=0, test=0, official RUL=0.
- Exact constant training sensors: none.
- Near-constant training sensors (modal share >= 99.9%): none.
- Shortest test engines by cycle count: 83 (21 cycles), 59 (22 cycles), 28 (23 cycles), 201 (25 cycles), 122 (29 cycles), 223 (29 cycles), 205 (31 cycles), 218 (33 cycles), 165 (35 cycles), 249 (36 cycles).
- Training raw RUL distribution (cycles): min=0, median=103.0, max=377; clipped-at-125 median=103.0.
- Official test RUL distribution (cycles): min=6, median=80.0, max=194; test engine ordering check=unit ids 1..N.
- Operating-setting cluster row counts: train=0:13458, 1:8044, 2:8122, 3:8002, 4:8096, 5:8037; test=0:8483, 1:5148, 2:5063, 3:5042, 4:5107, 5:5148.

### FD003 details

- Operating conditions expected: 1; distinct training setting triplets rounded to 4 decimals: 1479.
- Columns: unit, cycle, op1, op2, op3, s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12, s13, s14, s15, s16, s17, s18, s19, s20, s21. Training dtypes: float64=22, int64=4; test dtypes: float64=22, int64=4.
- Missing values: train=0, test=0, official RUL=0.
- Exact constant training sensors: s1, s5, s16, s18, s19.
- Near-constant training sensors (modal share >= 99.9%): s1 (100.0000% modal value), s5 (100.0000% modal value), s16 (100.0000% modal value), s18 (100.0000% modal value), s19 (100.0000% modal value).
- Shortest test engines by cycle count: 52 (38 cycles), 88 (41 cycles), 37 (47 cycles), 54 (50 cycles), 91 (56 cycles), 47 (56 cycles), 6 (64 cycles), 13 (65 cycles), 4 (68 cycles), 74 (68 cycles).
- Training raw RUL distribution (cycles): min=0, median=123.0, max=524; clipped-at-125 median=123.0.
- Official test RUL distribution (cycles): min=6, median=77.5, max=145; test engine ordering check=unit ids 1..N.
- Operating-setting cluster row counts: not applicable (single operating condition).

### FD004 details

- Operating conditions expected: 6; distinct training setting triplets rounded to 4 decimals: 10232.
- Columns: unit, cycle, op1, op2, op3, s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12, s13, s14, s15, s16, s17, s18, s19, s20, s21. Training dtypes: float64=22, int64=4; test dtypes: float64=22, int64=4.
- Missing values: train=0, test=0, official RUL=0.
- Exact constant training sensors: none.
- Near-constant training sensors (modal share >= 99.9%): none.
- Shortest test engines by cycle count: 204 (19 cycles), 141 (19 cycles), 28 (20 cycles), 229 (20 cycles), 125 (21 cycles), 10 (23 cycles), 19 (24 cycles), 156 (28 cycles), 239 (28 cycles), 246 (29 cycles).
- Training raw RUL distribution (cycles): min=0, median=122.0, max=542; clipped-at-125 median=122.0.
- Official test RUL distribution (cycles): min=6, median=88.0, max=195; test engine ordering check=unit ids 1..N.
- Operating-setting cluster row counts: train=0:15395, 1:9224, 2:9139, 3:9091, 4:9238, 5:9162; test=0:10382, 1:6185, 2:6107, 3:6254, 4:6054, 5:6232.

## Deviations from `CMAPSS/README.md` expectations

- FD004: train engines expected 248, observed 249.
- FD004: test engines expected 249, observed 248.
- FD004: official RUL rows expected 249, observed 248.

The expected 12 data files, `readme.txt`, and `Damage Propagation Modeling.pdf` are all present. Exact constants and near-constants above are reported for audit; protocol preprocessing must identify constants on each model's training-engine split.

## Generated figures

- Four `sensor_trajectories_FD00X.png` files (21 sensor channels, three deterministic training engines each).
- Four `life_lengths_FD00X.png` histograms (train and test).
- Four `sensor_rul_correlations_FD00X.png` sensor/RUL correlation charts.
- `operating_clusters_FD002.png` and `operating_clusters_FD004.png` (three operating-setting projections).
