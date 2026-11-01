# Ensemble methods

Official method selected by validation RMSE: **stacking**.

Included members: 01_lightgbm, 02_lstm, 03_bilstm_attention, 04_cnn1d, 05_transformer, 06_autoencoder, 07_cnn_transformer.
Excluded models: none.

## Validation-fitted parameters

Weighted-average weights: `{'01_lightgbm': 0.04431214883646999, '02_lstm': 0.5615665794676109, '03_bilstm_attention': 0.16296416317188794, '04_cnn1d': 0.0, '05_transformer': 0.19037339971014247, '06_autoencoder': 2.5796855653179183e-14, '07_cnn_transformer': 0.04078370881386309}`
Positive Ridge coefficients: `{'01_lightgbm': 0.12376195719883232, '02_lstm': 0.55060456853577, '03_bilstm_attention': 0.19109237316278466, '04_cnn1d': 0.0, '05_transformer': 0.101086835496813, '06_autoencoder': 0.0, '07_cnn_transformer': 0.053975774936441984}`
Positive Ridge intercept: `-3.50595632`

## Metrics

| Method | Split | RMSE | MAE | MSE | NASA score | R² |
|---|---|---:|---:|---:|---:|---:|
| weighted_average | val | 9.1068 | 6.0010 | 82.9339 | 7011.7983 | 0.9508 |
| weighted_average | test_raw | 13.9155 | 9.9395 | 193.6401 | 334.1928 | 0.8870 |
| weighted_average | test_clipped | 12.4615 | 8.3827 | 155.2899 | 299.3899 | 0.8988 |
| stacking | val | 8.9507 | 6.2081 | 80.1147 | 6512.2804 | 0.9525 |
| stacking | test_raw | 13.9808 | 10.2561 | 195.4627 | 319.1018 | 0.8859 |
| stacking | test_clipped | 12.4056 | 8.6961 | 153.8993 | 281.3708 | 0.8997 |

## Validation member error correlations

| Model | 01_lightgbm | 02_lstm | 03_bilstm_attention | 04_cnn1d | 05_transformer | 06_autoencoder | 07_cnn_transformer |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01_lightgbm | 1.0000 | 0.6632 | 0.7528 | 0.7373 | 0.7694 | 0.7158 | 0.6647 |
| 02_lstm | 0.6632 | 1.0000 | 0.7417 | 0.6751 | 0.7270 | 0.6172 | 0.7303 |
| 03_bilstm_attention | 0.7528 | 0.7417 | 1.0000 | 0.6691 | 0.8636 | 0.7044 | 0.7193 |
| 04_cnn1d | 0.7373 | 0.6751 | 0.6691 | 1.0000 | 0.6339 | 0.7419 | 0.7274 |
| 05_transformer | 0.7694 | 0.7270 | 0.8636 | 0.6339 | 1.0000 | 0.6401 | 0.7414 |
| 06_autoencoder | 0.7158 | 0.6172 | 0.7044 | 0.7419 | 0.6401 | 1.0000 | 0.5958 |
| 07_cnn_transformer | 0.6647 | 0.7303 | 0.7193 | 0.7274 | 0.7414 | 0.5958 | 1.0000 |
