# Native model catalog

Canonical application catalog: ml/registry/catalog.json; 168 routes, 813 integrity files. Every entry was actually inferred on CPU. Native hierarchy is retained under ml/artifacts/cmapss for relative-loader compatibility. Exact-run historical metrics remain labeled archival; unavailable metrics are never borrowed from another seed.

| Family / variant | FD001 | FD002 | FD003 | FD004 |
| --- | --- | --- | --- | --- |
| 01_lightgbm / original | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |
| 01_lightgbm / tuned | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |
| 01_lightgbm_quantile / tuned | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |
| 01_lightgbm_quantile_legacy / legacy_quantile | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |
| 02_lstm / saved | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |
| 03_bilstm_attention / saved | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |
| 04_cnn1d / saved | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |
| 05_transformer / saved | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |
| 06_autoencoder / anomaly | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |
| 06_autoencoder_rul_legacy / legacy_rul | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |
| 07_cnn_transformer / saved | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |
| 08_ensemble / saved | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |
| 08_ensemble_member_spread / saved | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |
| 09_ts_degradation / saved | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED | 3/3 INFERRED |

Cells cover seeds 42/43/44. All nine families, original/tuned LightGBM, autoencoder RUL versus anomaly, original/calibrated quantiles and member-spread variants remain distinct. Native output shape, finite values, dataset/seed/cycle units and interval order were validated. Legacy path adapters preserve original code beside adapted loaders. No fitted object or output math is changed.

Saved defaults use the original validation-selection policy. First source engine outputs below are fresh inference, not new evaluation metrics:

| Dataset | Exact model ID | Operating cycles |
| --- | --- | ---: |
| FD001 | fd001-01_lightgbm-s42 | 115.3478990753549 |
| FD002 | fd002-08_ensemble-s44 | 11.592229512416276 |
| FD003 | fd003-08_ensemble-s42 | 51.46118890357053 |
| FD004 | fd004-08_ensemble-s42 | 25.05196696607433 |

The separate HTTP smoke explicitly selected FD003 LightGBM and returned 43.38973340387454 cycles; it is a different model from that dataset default.

Parity: 44 independent primary comparisons within 1e-8; remaining routes inferred/hash-verified. The legacy autoencoder archival CSV tolerance failed while the worst-case exact original/consolidated CPU pair agreed. See TEST_EVIDENCE.md. No retraining, test tuning, recalibration, calendar conversion or output recapping. Compatible-format user declaration does not validate transfer to a different machine.
