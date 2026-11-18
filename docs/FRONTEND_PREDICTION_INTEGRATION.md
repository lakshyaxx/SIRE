# Preserved native prediction integration

The delivered RUL workspace wraps the original real Predictions controller. Four datasets remain independent; source histories, matching preprocessing, all catalog entries, model identity/digest, seed, raw sensor chart, RUL in operating cycles, saved interval method, warnings and separate anomaly output are preserved. Compatible CSV ingestion requires exact unit/cycle/op1–op3/s1–s21 schema and explicit NASA compatibility. Generic industrial telemetry is preview-only and cannot be submitted as C-MAPSS input. Comparison runs selected saved models on the same source/dataset; dataset changes clear prior results. Discussion passes the actual prediction ID to chat.

## Actual HTTP inference (disposable QA database)

These are genuine saved NASA histories and existing trained models, not synthetic oil-rig inputs. No retraining or tuning.

| Dataset | Selected role | Actual model ID | Seconds | Result |
| --- | --- | --- | --- | --- |
| FD001 | low_latency | `fd001-01_lightgbm-s42` | 5.914702 | passed |
| FD001 | advanced | `fd001-08_ensemble-s42` | 13.416326 | passed |
| FD001 | deep | `fd001-03_bilstm_attention-s42` | 10.542315 | passed |
| FD002 | low_latency | `fd002-01_lightgbm-original-s42` | 5.307294 | passed |
| FD002 | advanced | `fd002-08_ensemble-s44` | 11.327554 | passed |
| FD002 | deep | `fd002-03_bilstm_attention-s42` | 9.396255 | passed |
| FD003 | low_latency | `fd003-01_lightgbm-original-s42` | 4.400926 | passed |
| FD003 | advanced | `fd003-08_ensemble-s42` | 9.652971 | passed |
| FD003 | deep | `fd003-03_bilstm_attention-s42` | 8.549744 | passed |
| FD004 | low_latency | `fd004-01_lightgbm-original-s42` | 4.873877 | passed |
| FD004 | advanced | `fd004-08_ensemble-s42` | 10.850108 | passed |
| FD004 | deep | `fd004-03_bilstm_attention-s42` | 9.123490 | passed |

Browser checks separately exercised FD001 default inference and two LightGBM seeds (115.35 and 114.51 displayed cycles at source cycle31), then switched to FD004, verified stale results cleared and obtained 28.68 displayed cycles at source cycle230. Display values are rounded by the existing UI; exact persisted results/provenance are in the private network JSON. This does not claim that all 168 catalog entries were browser-clicked during this integration. The fresh preservation audit verifies all813 protected native-file hashes.

NASA simulation output is not a maintenance limit, wall-clock lifespan or diagnosis of an uploaded photograph. Original artifacts, dependencies and archival comparison findings remain unchanged.
