# Ensemble methods

Official method selected by validation RMSE: **stacking**.

Included members: 01_lightgbm, 02_lstm, 03_bilstm_attention, 04_cnn1d, 05_transformer, 06_autoencoder, 07_cnn_transformer.
Excluded models: none.

## Validation-fitted parameters

Weighted-average weights: `{'01_lightgbm': 0.08250481464188741, '02_lstm': 0.6016008297118773, '03_bilstm_attention': 0.1766481395090679, '04_cnn1d': 3.4045648420392083e-16, '05_transformer': 0.13364109262450394, '06_autoencoder': 0.005605123512639536, '07_cnn_transformer': 2.356821792337489e-14}`
Positive Ridge coefficients: `{'01_lightgbm': 0.05772952531952299, '02_lstm': 0.645219331464134, '03_bilstm_attention': 0.12093931880103402, '04_cnn1d': 0.07771162623557396, '05_transformer': 0.12649689104948805, '06_autoencoder': 0.019876736522304532, '07_cnn_transformer': 0.0}`
Positive Ridge intercept: `-3.84099099`

## Metrics

| Method | Split | RMSE | MAE | MSE | NASA score | R² |
|---|---|---:|---:|---:|---:|---:|
| weighted_average | val | 8.9098 | 6.4143 | 79.3839 | 5993.4480 | 0.9529 |
| weighted_average | test_raw | 14.3135 | 10.0316 | 204.8763 | 380.3019 | 0.8804 |
| weighted_average | test_clipped | 12.5706 | 8.4716 | 158.0197 | 336.8059 | 0.8970 |
| stacking | val | 8.7608 | 5.9605 | 76.7521 | 5928.7877 | 0.9545 |
| stacking | test_raw | 14.6006 | 10.3190 | 213.1777 | 444.4703 | 0.8756 |
| stacking | test_clipped | 13.0145 | 8.7590 | 169.3773 | 403.9513 | 0.8896 |

## Validation member error correlations

| Model | 01_lightgbm | 02_lstm | 03_bilstm_attention | 04_cnn1d | 05_transformer | 06_autoencoder | 07_cnn_transformer |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01_lightgbm | 1.0000 | 0.6844 | 0.7300 | 0.6798 | 0.7878 | 0.6977 | 0.7373 |
| 02_lstm | 0.6844 | 1.0000 | 0.7454 | 0.5795 | 0.7603 | 0.6032 | 0.7102 |
| 03_bilstm_attention | 0.7300 | 0.7454 | 1.0000 | 0.5545 | 0.8344 | 0.5531 | 0.7826 |
| 04_cnn1d | 0.6798 | 0.5795 | 0.5545 | 1.0000 | 0.5725 | 0.7635 | 0.6778 |
| 05_transformer | 0.7878 | 0.7603 | 0.8344 | 0.5725 | 1.0000 | 0.5600 | 0.8022 |
| 06_autoencoder | 0.6977 | 0.6032 | 0.5531 | 0.7635 | 0.5600 | 1.0000 | 0.6239 |
| 07_cnn_transformer | 0.7373 | 0.7102 | 0.7826 | 0.6778 | 0.8022 | 0.6239 | 1.0000 |
