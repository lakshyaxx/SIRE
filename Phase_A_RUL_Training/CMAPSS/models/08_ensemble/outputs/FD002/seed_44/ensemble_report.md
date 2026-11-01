# Ensemble methods

Official method selected by validation RMSE: **stacking**.

Included members: 01_lightgbm, 02_lstm, 03_bilstm_attention, 04_cnn1d, 05_transformer, 06_autoencoder, 07_cnn_transformer.
Excluded models: none.

## Validation-fitted parameters

Weighted-average weights: `{'01_lightgbm': 0.07726353775447703, '02_lstm': 0.7682871299807422, '03_bilstm_attention': 0.06963354547900624, '04_cnn1d': 5.168825835398824e-13, '05_transformer': 0.08481578678518625, '06_autoencoder': 0.0, '07_cnn_transformer': 7.142770761708101e-14}`
Positive Ridge coefficients: `{'01_lightgbm': 0.09461961402686428, '02_lstm': 0.7751791515494026, '03_bilstm_attention': 0.07214843098424792, '04_cnn1d': 0.0, '05_transformer': 0.07387594744930388, '06_autoencoder': 0.0, '07_cnn_transformer': 0.0}`
Positive Ridge intercept: `-1.35824914`

## Metrics

| Method | Split | RMSE | MAE | MSE | NASA score | R² |
|---|---|---:|---:|---:|---:|---:|
| weighted_average | val | 12.1864 | 8.5242 | 148.5088 | 32193.7253 | 0.9145 |
| weighted_average | test_raw | 25.2388 | 16.3632 | 636.9975 | 6692.7900 | 0.7798 |
| weighted_average | test_clipped | 12.2991 | 8.8690 | 151.2687 | 695.6826 | 0.9180 |
| stacking | val | 12.1713 | 8.3528 | 148.1396 | 32617.2559 | 0.9148 |
| stacking | test_raw | 25.1127 | 16.3022 | 630.6458 | 6544.2349 | 0.7819 |
| stacking | test_clipped | 12.3174 | 8.8091 | 151.7173 | 703.0005 | 0.9177 |

## Validation member error correlations

| Model | 01_lightgbm | 02_lstm | 03_bilstm_attention | 04_cnn1d | 05_transformer | 06_autoencoder | 07_cnn_transformer |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01_lightgbm | 1.0000 | 0.7658 | 0.8215 | 0.7786 | 0.8272 | 0.8016 | 0.8311 |
| 02_lstm | 0.7658 | 1.0000 | 0.7930 | 0.6478 | 0.7753 | 0.7709 | 0.7296 |
| 03_bilstm_attention | 0.8215 | 0.7930 | 1.0000 | 0.6529 | 0.8788 | 0.8495 | 0.7913 |
| 04_cnn1d | 0.7786 | 0.6478 | 0.6529 | 1.0000 | 0.6686 | 0.6789 | 0.7817 |
| 05_transformer | 0.8272 | 0.7753 | 0.8788 | 0.6686 | 1.0000 | 0.8243 | 0.7998 |
| 06_autoencoder | 0.8016 | 0.7709 | 0.8495 | 0.6789 | 0.8243 | 1.0000 | 0.7834 |
| 07_cnn_transformer | 0.8311 | 0.7296 | 0.7913 | 0.7817 | 0.7998 | 0.7834 | 1.0000 |
