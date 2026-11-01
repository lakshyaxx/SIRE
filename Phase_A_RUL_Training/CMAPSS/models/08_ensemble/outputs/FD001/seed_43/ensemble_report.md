# Ensemble methods

Official method selected by validation RMSE: **stacking**.

Included members: 01_lightgbm, 02_lstm, 03_bilstm_attention, 04_cnn1d, 05_transformer, 06_autoencoder, 07_cnn_transformer.
Excluded models: none.

## Validation-fitted parameters

Weighted-average weights: `{'01_lightgbm': 0.1641966790411275, '02_lstm': 0.5017877912656687, '03_bilstm_attention': 1.6080311676692985e-20, '04_cnn1d': 1.4701315652018043e-14, '05_transformer': 0.3340155296931752, '06_autoencoder': 0.0, '07_cnn_transformer': 1.3923672410044969e-14}`
Positive Ridge coefficients: `{'01_lightgbm': 0.1824062073818052, '02_lstm': 0.4934289698919701, '03_bilstm_attention': 0.0, '04_cnn1d': 0.0, '05_transformer': 0.3350862203033206, '06_autoencoder': 0.0, '07_cnn_transformer': 0.0}`
Positive Ridge intercept: `-1.70948024`

## Metrics

| Method | Split | RMSE | MAE | MSE | NASA score | R² |
|---|---|---:|---:|---:|---:|---:|
| weighted_average | val | 10.5732 | 7.2416 | 111.7924 | 7166.9130 | 0.9361 |
| weighted_average | test_raw | 14.1412 | 10.7873 | 199.9730 | 286.0552 | 0.8842 |
| weighted_average | test_clipped | 12.9857 | 9.7173 | 168.6281 | 258.4397 | 0.8950 |
| stacking | val | 10.5362 | 7.1954 | 111.0117 | 6938.5923 | 0.9365 |
| stacking | test_raw | 14.1250 | 10.5021 | 199.5143 | 278.3713 | 0.8845 |
| stacking | test_clipped | 12.9317 | 9.4321 | 167.2292 | 249.8082 | 0.8959 |

## Validation member error correlations

| Model | 01_lightgbm | 02_lstm | 03_bilstm_attention | 04_cnn1d | 05_transformer | 06_autoencoder | 07_cnn_transformer |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01_lightgbm | 1.0000 | 0.6594 | 0.8566 | 0.7044 | 0.7537 | 0.7790 | 0.7406 |
| 02_lstm | 0.6594 | 1.0000 | 0.7036 | 0.5511 | 0.6856 | 0.5528 | 0.6466 |
| 03_bilstm_attention | 0.8566 | 0.7036 | 1.0000 | 0.6962 | 0.8243 | 0.7550 | 0.8094 |
| 04_cnn1d | 0.7044 | 0.5511 | 0.6962 | 1.0000 | 0.5452 | 0.7452 | 0.7282 |
| 05_transformer | 0.7537 | 0.6856 | 0.8243 | 0.5452 | 1.0000 | 0.6022 | 0.6960 |
| 06_autoencoder | 0.7790 | 0.5528 | 0.7550 | 0.7452 | 0.6022 | 1.0000 | 0.7078 |
| 07_cnn_transformer | 0.7406 | 0.6466 | 0.8094 | 0.7282 | 0.6960 | 0.7078 | 1.0000 |
