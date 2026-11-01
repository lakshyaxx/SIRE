# Ensemble methods

Official method selected by validation RMSE: **weighted_average**.

Included members: 01_lightgbm, 02_lstm, 03_bilstm_attention, 04_cnn1d, 05_transformer, 06_autoencoder, 07_cnn_transformer.
Excluded models: none.

## Validation-fitted parameters

Weighted-average weights: `{'01_lightgbm': 0.09496596049531413, '02_lstm': 0.48307084306016324, '03_bilstm_attention': 0.019593214423980265, '04_cnn1d': 0.0, '05_transformer': 0.40236998202054236, '06_autoencoder': 0.0, '07_cnn_transformer': 0.0}`
Positive Ridge coefficients: `{'01_lightgbm': 0.1681804960087836, '02_lstm': 0.37678964903033996, '03_bilstm_attention': 0.15962198458389884, '04_cnn1d': 0.0, '05_transformer': 0.30698042494653743, '06_autoencoder': 0.0, '07_cnn_transformer': 0.015186555356930058}`
Positive Ridge intercept: `-1.63206115`

## Metrics

| Method | Split | RMSE | MAE | MSE | NASA score | R² |
|---|---|---:|---:|---:|---:|---:|
| weighted_average | val | 10.5631 | 7.6059 | 111.5798 | 6582.9084 | 0.9362 |
| weighted_average | test_raw | 14.1637 | 10.7683 | 200.6111 | 275.3407 | 0.8838 |
| weighted_average | test_clipped | 12.7823 | 9.6983 | 163.3882 | 240.4047 | 0.8983 |
| stacking | val | 10.6387 | 7.4015 | 113.1811 | 7197.4699 | 0.9353 |
| stacking | test_raw | 13.8570 | 10.4367 | 192.0152 | 275.9192 | 0.8888 |
| stacking | test_clipped | 12.6056 | 9.3667 | 158.9001 | 246.3223 | 0.9011 |

## Validation member error correlations

| Model | 01_lightgbm | 02_lstm | 03_bilstm_attention | 04_cnn1d | 05_transformer | 06_autoencoder | 07_cnn_transformer |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01_lightgbm | 1.0000 | 0.7478 | 0.7997 | 0.7465 | 0.7852 | 0.7882 | 0.7695 |
| 02_lstm | 0.7478 | 1.0000 | 0.7236 | 0.6723 | 0.7320 | 0.6665 | 0.6989 |
| 03_bilstm_attention | 0.7997 | 0.7236 | 1.0000 | 0.6734 | 0.7830 | 0.6938 | 0.7400 |
| 04_cnn1d | 0.7465 | 0.6723 | 0.6734 | 1.0000 | 0.5898 | 0.6976 | 0.8309 |
| 05_transformer | 0.7852 | 0.7320 | 0.7830 | 0.5898 | 1.0000 | 0.6667 | 0.7307 |
| 06_autoencoder | 0.7882 | 0.6665 | 0.6938 | 0.6976 | 0.6667 | 1.0000 | 0.6975 |
| 07_cnn_transformer | 0.7695 | 0.6989 | 0.7400 | 0.8309 | 0.7307 | 0.6975 | 1.0000 |
