# Ensemble methods

Official method selected by validation RMSE: **weighted_average**.

Included members: 01_lightgbm, 02_lstm, 03_bilstm_attention, 04_cnn1d, 05_transformer, 06_autoencoder, 07_cnn_transformer.
Excluded models: none.

## Validation-fitted parameters

Weighted-average weights: `{'01_lightgbm': 0.008897833904366579, '02_lstm': 0.6001998300446645, '03_bilstm_attention': 0.0, '04_cnn1d': 1.7984187298402314e-12, '05_transformer': 0.34746309893623406, '06_autoencoder': 4.1390606402900014e-13, '07_cnn_transformer': 0.0434392371125226}`
Positive Ridge coefficients: `{'01_lightgbm': 0.014199407939712434, '02_lstm': 0.6445214160823556, '03_bilstm_attention': 0.014172244021878251, '04_cnn1d': 0.0, '05_transformer': 0.2790314674985167, '06_autoencoder': 0.0, '07_cnn_transformer': 0.03860109676691412}`
Positive Ridge intercept: `0.84653996`

## Metrics

| Method | Split | RMSE | MAE | MSE | NASA score | R² |
|---|---|---:|---:|---:|---:|---:|
| weighted_average | val | 13.7651 | 7.8917 | 189.4778 | 238827.0465 | 0.8846 |
| weighted_average | test_raw | 25.9746 | 18.3791 | 674.6791 | 4613.6363 | 0.7731 |
| weighted_average | test_clipped | 13.8122 | 9.6903 | 190.7775 | 1055.6422 | 0.8967 |
| stacking | val | 13.7700 | 8.0217 | 189.6129 | 234510.1422 | 0.8845 |
| stacking | test_raw | 26.0894 | 18.5668 | 680.6585 | 4640.6019 | 0.7710 |
| stacking | test_clipped | 13.8671 | 9.8742 | 192.2974 | 1056.0401 | 0.8959 |

## Validation member error correlations

| Model | 01_lightgbm | 02_lstm | 03_bilstm_attention | 04_cnn1d | 05_transformer | 06_autoencoder | 07_cnn_transformer |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01_lightgbm | 1.0000 | 0.7973 | 0.8753 | 0.8062 | 0.8758 | 0.8593 | 0.7823 |
| 02_lstm | 0.7973 | 1.0000 | 0.8586 | 0.7381 | 0.8058 | 0.8159 | 0.7835 |
| 03_bilstm_attention | 0.8753 | 0.8586 | 1.0000 | 0.7732 | 0.9026 | 0.8909 | 0.8226 |
| 04_cnn1d | 0.8062 | 0.7381 | 0.7732 | 1.0000 | 0.7440 | 0.8037 | 0.7905 |
| 05_transformer | 0.8758 | 0.8058 | 0.9026 | 0.7440 | 1.0000 | 0.8768 | 0.8024 |
| 06_autoencoder | 0.8593 | 0.8159 | 0.8909 | 0.8037 | 0.8768 | 1.0000 | 0.8207 |
| 07_cnn_transformer | 0.7823 | 0.7835 | 0.8226 | 0.7905 | 0.8024 | 0.8207 | 1.0000 |
