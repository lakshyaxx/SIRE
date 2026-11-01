# Ensemble methods

Official method selected by validation RMSE: **stacking**.

Included members: 01_lightgbm, 02_lstm, 03_bilstm_attention, 04_cnn1d, 05_transformer, 06_autoencoder, 07_cnn_transformer.
Excluded models: none.

## Validation-fitted parameters

Weighted-average weights: `{'01_lightgbm': 0.10119555216598289, '02_lstm': 0.6272731663915415, '03_bilstm_attention': 0.02966032268162569, '04_cnn1d': 2.822860859343998e-14, '05_transformer': 0.2418709587608182, '06_autoencoder': 0.0, '07_cnn_transformer': 3.553388085552052e-15}`
Positive Ridge coefficients: `{'01_lightgbm': 0.13519345774900152, '02_lstm': 0.5823674266110644, '03_bilstm_attention': 0.0714842069425581, '04_cnn1d': 0.0, '05_transformer': 0.2448625170544095, '06_autoencoder': 0.004464239509541842, '07_cnn_transformer': 0.0}`
Positive Ridge intercept: `-2.71342538`

## Metrics

| Method | Split | RMSE | MAE | MSE | NASA score | R² |
|---|---|---:|---:|---:|---:|---:|
| weighted_average | val | 12.5925 | 9.1289 | 158.5701 | 32851.9966 | 0.9088 |
| weighted_average | test_raw | 26.1420 | 17.0433 | 683.4020 | 7338.0771 | 0.7637 |
| weighted_average | test_clipped | 12.8969 | 9.5491 | 166.3289 | 702.2221 | 0.9098 |
| stacking | val | 12.5383 | 8.5577 | 157.2080 | 34841.4555 | 0.9095 |
| stacking | test_raw | 25.6374 | 16.9613 | 657.2738 | 6648.5869 | 0.7727 |
| stacking | test_clipped | 12.8469 | 9.4671 | 165.0418 | 731.2623 | 0.9105 |

## Validation member error correlations

| Model | 01_lightgbm | 02_lstm | 03_bilstm_attention | 04_cnn1d | 05_transformer | 06_autoencoder | 07_cnn_transformer |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01_lightgbm | 1.0000 | 0.7809 | 0.7768 | 0.7656 | 0.8262 | 0.8000 | 0.8033 |
| 02_lstm | 0.7809 | 1.0000 | 0.7833 | 0.6690 | 0.7904 | 0.7722 | 0.7179 |
| 03_bilstm_attention | 0.7768 | 0.7833 | 1.0000 | 0.6503 | 0.8269 | 0.8180 | 0.7432 |
| 04_cnn1d | 0.7656 | 0.6690 | 0.6503 | 1.0000 | 0.6452 | 0.6712 | 0.7683 |
| 05_transformer | 0.8262 | 0.7904 | 0.8269 | 0.6452 | 1.0000 | 0.8257 | 0.7547 |
| 06_autoencoder | 0.8000 | 0.7722 | 0.8180 | 0.6712 | 0.8257 | 1.0000 | 0.7489 |
| 07_cnn_transformer | 0.8033 | 0.7179 | 0.7432 | 0.7683 | 0.7547 | 0.7489 | 1.0000 |
