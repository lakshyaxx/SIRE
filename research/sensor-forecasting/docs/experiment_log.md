# Experiment log
| Date | Dataset/subset | Model | Seed | RMSE | NASA score | Notes |
|---|---|---|---|---|---|---|

| 2026-10-27 | C-MAPSS/FD001 | LightGBM validation (terminal only; superseded) | 42 | 1.7841 | 3.3081 | MAE 1.4784; window 30; engine holdout |
| 2026-10-27 | C-MAPSS/FD001 | LightGBM validation (terminal only; superseded) | 43 | 1.6877 | 3.2042 | MAE 1.4484; window 30; engine holdout |
| 2026-10-27 | C-MAPSS/FD001 | LightGBM validation (terminal only; superseded) | 44 | 1.5933 | 2.8209 | MAE 1.2727; window 30; engine holdout |
| 2026-10-27 | C-MAPSS/FD001 | LightGBM official test (clipped at 125; superseded) | 42,43,44 | 12.7123 | 246.3574 | MAE 9.5341; terminal window per engine |

| 2026-10-28 | C-MAPSS/FD001 | LightGBM validation all windows | 42 | 12.1780 | 9325.1010 | MAE 8.7704; engine holdout; window 30 |
| 2026-10-28 | C-MAPSS/FD001 | LightGBM validation terminal per engine | 42 | 1.7841 | 3.3081 | MAE 1.4784; engine holdout; window 30 |
| 2026-10-28 | C-MAPSS/FD001 | LightGBM validation all windows | 43 | 12.1052 | 9286.1758 | MAE 8.6502; engine holdout; window 30 |
| 2026-10-28 | C-MAPSS/FD001 | LightGBM validation terminal per engine | 43 | 1.6877 | 3.2042 | MAE 1.4484; engine holdout; window 30 |
| 2026-10-28 | C-MAPSS/FD001 | LightGBM validation all windows | 44 | 12.0107 | 9454.2132 | MAE 8.5709; engine holdout; window 30 |
| 2026-10-28 | C-MAPSS/FD001 | LightGBM validation terminal per engine | 44 | 1.5933 | 2.8209 | MAE 1.2727; engine holdout; window 30 |
| 2026-10-28 | C-MAPSS/FD001 | LightGBM official test raw RUL | ensemble | 14.0138 | 279.4752 | MAE 10.6041; terminal window per engine |
| 2026-10-28 | C-MAPSS/FD001 | LightGBM official test RUL clipped at 125 | ensemble | 12.7123 | 246.3574 | MAE 9.5341; terminal window per engine |

2026-11-22 repository verification. Ran the existing FD001 engine 1, sensor 2
stationarity analysis from a separate working directory and verified that it
wrote its CSV and plot to an isolated temporary run directory.

## 2026-11-23 sensor benchmark

FD001 engine 1, cycles 1–153 observed and 154–192 scored. Sensor RMSE is in
native units. NASA score applies to the separate RUL task.

| Model | Sensor 2 RMSE | Sensor 3 RMSE |
| --- | ---: | ---: |
| ARMA | 0.685414 | |
| ARIMAX | 0.457159 | |
| SARIMAX | 0.460752 | |
| VAR | 0.514314 | 5.746134 |
| VARMA | 0.667744 | 7.668164 |
| VARIMA | 0.548278 | 6.416757 |
| VARMAX | 0.496187 | 7.248371 |
| Holt-Winters | 0.543930 | |
| TFT CPU smoke, seed 42 | 0.875687 | 9.607451 |

The combined run is in `results/runs/sensor-skh5xq1s` with six classical
baselines and all nine additions. Full TFT training was deferred. The
training-prefix ACF of first differences at lag 10 was −0.114 against the
±0.159 screening bound. For both targets, the VARIMA ADF p-values were
above 0.05 in levels and below 0.05 after first differencing.

Verification runs `sensor-20u7rjg7`, `sensor-shbg0afe`, and
`sensor-l9588gcg` exposed a NumPy integer serialization error, missing
optional TFT dependencies, and encoding of unseen TFT engine groups,
respectively. After those fixes, the statistical-only run
`sensor-dbcylcov` and TFT CPU smoke run `sensor-a18p6pw7` completed.
