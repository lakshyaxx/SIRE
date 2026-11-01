# Ensemble methods

Official method selected by validation RMSE: **stacking**.

Included members: 01_lightgbm, 02_lstm, 03_bilstm_attention, 04_cnn1d, 05_transformer, 06_autoencoder, 07_cnn_transformer.
Excluded models: none.

## Validation-fitted parameters

Weighted-average weights: `{'01_lightgbm': 0.08432745375192711, '02_lstm': 0.4352900872409285, '03_bilstm_attention': 0.13127242282342746, '04_cnn1d': 0.0, '05_transformer': 0.2917636082760825, '06_autoencoder': 0.05734642790763027, '07_cnn_transformer': 4.290968103943005e-15}`
Positive Ridge coefficients: `{'01_lightgbm': 0.1213483528119666, '02_lstm': 0.4157906730184065, '03_bilstm_attention': 0.17812259923513013, '04_cnn1d': 0.0, '05_transformer': 0.19679236080566184, '06_autoencoder': 0.11103892977590003, '07_cnn_transformer': 0.0}`
Positive Ridge intercept: `-2.17342257`

## Metrics

| Method | Split | RMSE | MAE | MSE | NASA score | R² |
|---|---|---:|---:|---:|---:|---:|
| weighted_average | val | 12.6854 | 8.8610 | 160.9203 | 35796.1662 | 0.9074 |
| weighted_average | test_raw | 26.0783 | 17.0610 | 680.0785 | 7774.9309 | 0.7649 |
| weighted_average | test_clipped | 13.1550 | 9.5668 | 173.0553 | 786.8008 | 0.9061 |
| stacking | val | 12.6714 | 8.7076 | 160.5647 | 36333.3640 | 0.9076 |
| stacking | test_raw | 26.0399 | 17.1501 | 678.0758 | 7756.1864 | 0.7655 |
| stacking | test_clipped | 13.2086 | 9.6559 | 174.4661 | 800.9539 | 0.9054 |

## Validation member error correlations

| Model | 01_lightgbm | 02_lstm | 03_bilstm_attention | 04_cnn1d | 05_transformer | 06_autoencoder | 07_cnn_transformer |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01_lightgbm | 1.0000 | 0.6948 | 0.8061 | 0.7779 | 0.8264 | 0.8405 | 0.8085 |
| 02_lstm | 0.6948 | 1.0000 | 0.7350 | 0.6412 | 0.6842 | 0.6972 | 0.6476 |
| 03_bilstm_attention | 0.8061 | 0.7350 | 1.0000 | 0.6912 | 0.8564 | 0.8545 | 0.7747 |
| 04_cnn1d | 0.7779 | 0.6412 | 0.6912 | 1.0000 | 0.6595 | 0.7004 | 0.7651 |
| 05_transformer | 0.8264 | 0.6842 | 0.8564 | 0.6595 | 1.0000 | 0.8542 | 0.7971 |
| 06_autoencoder | 0.8405 | 0.6972 | 0.8545 | 0.7004 | 0.8542 | 1.0000 | 0.8094 |
| 07_cnn_transformer | 0.8085 | 0.6476 | 0.7747 | 0.7651 | 0.7971 | 0.8094 | 1.0000 |
