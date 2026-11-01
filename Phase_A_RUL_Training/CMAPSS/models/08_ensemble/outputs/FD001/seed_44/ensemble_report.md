# Ensemble methods

Official method selected by validation RMSE: **stacking**.

Included members: 01_lightgbm, 02_lstm, 03_bilstm_attention, 04_cnn1d, 05_transformer, 06_autoencoder, 07_cnn_transformer.
Excluded models: none.

## Validation-fitted parameters

Weighted-average weights: `{'01_lightgbm': 0.1438893849639782, '02_lstm': 0.5430419670737381, '03_bilstm_attention': 0.0, '04_cnn1d': 0.0, '05_transformer': 0.3130686479622836, '06_autoencoder': 0.0, '07_cnn_transformer': 0.0}`
Positive Ridge coefficients: `{'01_lightgbm': 0.21768553923768588, '02_lstm': 0.5049075729140688, '03_bilstm_attention': 0.0, '04_cnn1d': 0.0, '05_transformer': 0.2928986223696838, '06_autoencoder': 0.0, '07_cnn_transformer': 0.0}`
Positive Ridge intercept: `-1.30240264`

## Metrics

| Method | Split | RMSE | MAE | MSE | NASA score | R² |
|---|---|---:|---:|---:|---:|---:|
| weighted_average | val | 10.4589 | 7.3213 | 109.3882 | 6690.9400 | 0.9375 |
| weighted_average | test_raw | 14.0277 | 10.1141 | 196.7756 | 283.6755 | 0.8861 |
| weighted_average | test_clipped | 12.7165 | 9.0441 | 161.7095 | 250.9156 | 0.8993 |
| stacking | val | 10.4566 | 7.2195 | 109.3400 | 6842.5325 | 0.9375 |
| stacking | test_raw | 13.8232 | 9.9565 | 191.0802 | 277.9872 | 0.8893 |
| stacking | test_clipped | 12.5485 | 8.8865 | 157.4640 | 247.0711 | 0.9019 |

## Validation member error correlations

| Model | 01_lightgbm | 02_lstm | 03_bilstm_attention | 04_cnn1d | 05_transformer | 06_autoencoder | 07_cnn_transformer |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01_lightgbm | 1.0000 | 0.6474 | 0.8202 | 0.7391 | 0.8129 | 0.7701 | 0.7679 |
| 02_lstm | 0.6474 | 1.0000 | 0.7732 | 0.5806 | 0.6744 | 0.5847 | 0.6776 |
| 03_bilstm_attention | 0.8202 | 0.7732 | 1.0000 | 0.6625 | 0.8567 | 0.7484 | 0.8324 |
| 04_cnn1d | 0.7391 | 0.5806 | 0.6625 | 1.0000 | 0.6604 | 0.7439 | 0.7692 |
| 05_transformer | 0.8129 | 0.6744 | 0.8567 | 0.6604 | 1.0000 | 0.7545 | 0.7796 |
| 06_autoencoder | 0.7701 | 0.5847 | 0.7484 | 0.7439 | 0.7545 | 1.0000 | 0.7707 |
| 07_cnn_transformer | 0.7679 | 0.6776 | 0.8324 | 0.7692 | 0.7796 | 0.7707 | 1.0000 |
