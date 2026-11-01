# Ensemble methods

Official method selected by validation RMSE: **stacking**.

Included members: 01_lightgbm, 02_lstm, 03_bilstm_attention, 04_cnn1d, 05_transformer, 06_autoencoder, 07_cnn_transformer.
Excluded models: none.

## Validation-fitted parameters

Weighted-average weights: `{'01_lightgbm': 0.07338571588847487, '02_lstm': 0.5382568247332598, '03_bilstm_attention': 0.2641109887441521, '04_cnn1d': 0.0, '05_transformer': 0.04726006415873283, '06_autoencoder': 0.03113449415100821, '07_cnn_transformer': 0.04585191232437228}`
Positive Ridge coefficients: `{'01_lightgbm': 0.058420622334388515, '02_lstm': 0.5495751622366449, '03_bilstm_attention': 0.20751120758367875, '04_cnn1d': 0.0, '05_transformer': 0.09819520942282257, '06_autoencoder': 0.03596263760526632, '07_cnn_transformer': 0.04468195552619828}`
Positive Ridge intercept: `1.36733755`

## Metrics

| Method | Split | RMSE | MAE | MSE | NASA score | R² |
|---|---|---:|---:|---:|---:|---:|
| weighted_average | val | 13.7974 | 7.9461 | 190.3690 | 233842.0560 | 0.8841 |
| weighted_average | test_raw | 26.2981 | 18.3924 | 691.5882 | 5215.1433 | 0.7674 |
| weighted_average | test_clipped | 14.1198 | 9.7214 | 199.3680 | 1228.1768 | 0.8921 |
| stacking | val | 13.7748 | 7.9001 | 189.7459 | 215911.0710 | 0.8845 |
| stacking | test_raw | 26.1007 | 18.4291 | 681.2466 | 5107.8223 | 0.7708 |
| stacking | test_clipped | 14.1539 | 9.7949 | 200.3334 | 1263.4931 | 0.8916 |

## Validation member error correlations

| Model | 01_lightgbm | 02_lstm | 03_bilstm_attention | 04_cnn1d | 05_transformer | 06_autoencoder | 07_cnn_transformer |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01_lightgbm | 1.0000 | 0.7341 | 0.8610 | 0.7985 | 0.8807 | 0.8388 | 0.8393 |
| 02_lstm | 0.7341 | 1.0000 | 0.8119 | 0.6640 | 0.7739 | 0.7708 | 0.7516 |
| 03_bilstm_attention | 0.8610 | 0.8119 | 1.0000 | 0.7651 | 0.9099 | 0.8768 | 0.8657 |
| 04_cnn1d | 0.7985 | 0.6640 | 0.7651 | 1.0000 | 0.7437 | 0.7917 | 0.8312 |
| 05_transformer | 0.8807 | 0.7739 | 0.9099 | 0.7437 | 1.0000 | 0.8470 | 0.8273 |
| 06_autoencoder | 0.8388 | 0.7708 | 0.8768 | 0.7917 | 0.8470 | 1.0000 | 0.8503 |
| 07_cnn_transformer | 0.8393 | 0.7516 | 0.8657 | 0.8312 | 0.8273 | 0.8503 | 1.0000 |
