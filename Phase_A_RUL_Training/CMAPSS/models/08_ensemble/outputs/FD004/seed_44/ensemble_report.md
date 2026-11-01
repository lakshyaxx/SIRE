# Ensemble methods

Official method selected by validation RMSE: **stacking**.

Included members: 01_lightgbm, 02_lstm, 03_bilstm_attention, 04_cnn1d, 05_transformer, 06_autoencoder, 07_cnn_transformer.
Excluded models: none.

## Validation-fitted parameters

Weighted-average weights: `{'01_lightgbm': 0.008102804355489285, '02_lstm': 0.5175066079763958, '03_bilstm_attention': 0.03397969597281568, '04_cnn1d': 0.0, '05_transformer': 0.2107563644112526, '06_autoencoder': 1.858543136671724e-14, '07_cnn_transformer': 0.22965452728402824}`
Positive Ridge coefficients: `{'01_lightgbm': 0.0009480372253684653, '02_lstm': 0.6169082144043628, '03_bilstm_attention': 0.12850647707755095, '04_cnn1d': 0.0, '05_transformer': 0.17498104788284835, '06_autoencoder': 0.0, '07_cnn_transformer': 0.09290193639614262}`
Positive Ridge intercept: `1.59701851`

## Metrics

| Method | Split | RMSE | MAE | MSE | NASA score | R² |
|---|---|---:|---:|---:|---:|---:|
| weighted_average | val | 13.6832 | 8.5641 | 187.2310 | 208904.3809 | 0.8860 |
| weighted_average | test_raw | 26.7707 | 18.7501 | 716.6683 | 5457.5711 | 0.7589 |
| weighted_average | test_clipped | 13.6584 | 10.0565 | 186.5532 | 835.7247 | 0.8990 |
| stacking | val | 13.4617 | 7.6542 | 181.2179 | 205140.7380 | 0.8897 |
| stacking | test_raw | 25.8661 | 18.3010 | 669.0566 | 4848.1988 | 0.7749 |
| stacking | test_clipped | 13.5489 | 9.6588 | 183.5734 | 918.2410 | 0.9006 |

## Validation member error correlations

| Model | 01_lightgbm | 02_lstm | 03_bilstm_attention | 04_cnn1d | 05_transformer | 06_autoencoder | 07_cnn_transformer |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01_lightgbm | 1.0000 | 0.7684 | 0.8238 | 0.7916 | 0.8594 | 0.8397 | 0.7803 |
| 02_lstm | 0.7684 | 1.0000 | 0.7967 | 0.7119 | 0.7677 | 0.7775 | 0.7781 |
| 03_bilstm_attention | 0.8238 | 0.7967 | 1.0000 | 0.7346 | 0.8281 | 0.8282 | 0.8466 |
| 04_cnn1d | 0.7916 | 0.7119 | 0.7346 | 1.0000 | 0.7035 | 0.7927 | 0.7454 |
| 05_transformer | 0.8594 | 0.7677 | 0.8281 | 0.7035 | 1.0000 | 0.8053 | 0.8080 |
| 06_autoencoder | 0.8397 | 0.7775 | 0.8282 | 0.7927 | 0.8053 | 1.0000 | 0.7907 |
| 07_cnn_transformer | 0.7803 | 0.7781 | 0.8466 | 0.7454 | 0.8080 | 0.7907 | 1.0000 |
