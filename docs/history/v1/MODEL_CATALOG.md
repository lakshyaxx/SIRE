# Model catalog

All registered routes were tested using engine 1 from the corresponding official test sensor history. RUL values below are fresh inference, not accuracy metrics; anomaly scores have separate units. Original byte locations remain authoritative.

| Dataset | Registered route | Seed | Task | CPU check | Native output |
| --- | --- | ---: | --- | --- | ---: |
| FD001 | 01_lightgbm | 42 | rul | ready | 115.347899 |
| FD001 | 02_lstm | 42 | rul | ready | 119.960062 |
| FD001 | 03_bilstm_attention | 43 | rul | ready | 115.714133 |
| FD001 | 04_cnn1d | 43 | rul | ready | 125.032887 |
| FD001 | 05_transformer | 42 | rul | ready | 113.172427 |
| FD001 | 07_cnn_transformer | 42 | rul | ready | 117.073946 |
| FD001 | 08_ensemble | 42 | rul | ready | 114.046988 |
| FD001 | 09_ts_degradation | 42 | rul | ready | 63.000000 |
| FD001 | 01_lightgbm_quantile | 42 | rul | ready | 115.347899 |
| FD001 | 08_ensemble_member_spread | 42 | rul | ready | 114.046988 |
| FD001 | 06_autoencoder | 42 | anomaly | ready | 0.087655 |
| FD002 | 01_lightgbm | 43 | rul | ready | 19.068519 |
| FD002 | 02_lstm | 44 | rul | ready | 12.565898 |
| FD002 | 03_bilstm_attention | 42 | rul | ready | 12.959297 |
| FD002 | 04_cnn1d | 43 | rul | ready | 22.310402 |
| FD002 | 05_transformer | 42 | rul | ready | 14.083947 |
| FD002 | 07_cnn_transformer | 44 | rul | ready | 16.732274 |
| FD002 | 08_ensemble | 44 | rul | ready | 11.592230 |
| FD002 | 09_ts_degradation | 42 | rul | ready | 11.000000 |
| FD002 | 01_lightgbm_quantile | 43 | rul | ready | 19.068519 |
| FD002 | 08_ensemble_member_spread | 44 | rul | ready | 11.592230 |
| FD002 | 06_autoencoder | 42 | anomaly | ready | 12.696116 |
| FD003 | 01_lightgbm | 42 | rul | ready | 43.389733 |
| FD003 | 02_lstm | 42 | rul | ready | 51.772658 |
| FD003 | 03_bilstm_attention | 43 | rul | ready | 48.645269 |
| FD003 | 04_cnn1d | 44 | rul | ready | 57.752751 |
| FD003 | 05_transformer | 42 | rul | ready | 49.686167 |
| FD003 | 07_cnn_transformer | 44 | rul | ready | 44.737883 |
| FD003 | 08_ensemble | 42 | rul | ready | 51.461189 |
| FD003 | 09_ts_degradation | 42 | rul | ready | 61.000000 |
| FD003 | 01_lightgbm_quantile | 42 | rul | ready | 43.389733 |
| FD003 | 08_ensemble_member_spread | 42 | rul | ready | 51.461189 |
| FD003 | 06_autoencoder | 42 | anomaly | ready | 1669.713571 |
| FD004 | 01_lightgbm | 42 | rul | ready | 32.158785 |
| FD004 | 02_lstm | 44 | rul | ready | 25.022788 |
| FD004 | 03_bilstm_attention | 42 | rul | ready | 24.990087 |
| FD004 | 04_cnn1d | 42 | rul | ready | 27.578846 |
| FD004 | 05_transformer | 43 | rul | ready | 26.828248 |
| FD004 | 07_cnn_transformer | 43 | rul | ready | 36.881007 |
| FD004 | 08_ensemble | 42 | rul | ready | 25.051967 |
| FD004 | 09_ts_degradation | 42 | rul | ready | 21.000000 |
| FD004 | 01_lightgbm_quantile | 42 | rul | ready | 32.158785 |
| FD004 | 08_ensemble_member_spread | 42 | rul | ready | 25.051967 |
| FD004 | 06_autoencoder | 42 | anomaly | ready | 3.751963 |

All nine families remain available. Ensemble member-spread routes intentionally reference the same ensemble native loader with uncertainty; they are separate registry routes, not additional independently trained model families. Full output/version/timings: `model_store/verification.json`. Exact file SHA-256 and fitted feature order: `model_store/manifest.json`.

Integrity: 790 inference files match the external pre-build snapshot. Bundle hash: `07ae6b6732be8154bf45e6cc3c3975b957c4891c19a4aa0b236bda8de7592417`.

Historic original and alternate-seed files remain preserved and hashed. The current app exposes the 44 selected registry routes. Unregistered original-only LightGBM variants, additional seeds and the historical autoencoder RUL head are not yet exposed; the anomaly variant is available. N-CMAPSS remains unsupported.
