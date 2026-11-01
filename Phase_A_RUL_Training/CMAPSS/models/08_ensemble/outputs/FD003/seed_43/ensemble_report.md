# Ensemble methods

Official method selected by validation RMSE: **stacking**.

Included members: 01_lightgbm, 02_lstm, 03_bilstm_attention, 04_cnn1d, 05_transformer, 06_autoencoder, 07_cnn_transformer.
Excluded models: none.

## Validation-fitted parameters

Weighted-average weights: `{'01_lightgbm': 0.06963984925136237, '02_lstm': 0.5819840525381864, '03_bilstm_attention': 0.030176593240716244, '04_cnn1d': 0.058747886936919694, '05_transformer': 0.25945161803281275, '06_autoencoder': 0.0, '07_cnn_transformer': 2.4274169310157938e-15}`
Positive Ridge coefficients: `{'01_lightgbm': 0.09996781787154184, '02_lstm': 0.5694950197463896, '03_bilstm_attention': 0.0, '04_cnn1d': 0.09327141078351832, '05_transformer': 0.2820296700926848, '06_autoencoder': 0.0019942612695642175, '07_cnn_transformer': 0.0}`
Positive Ridge intercept: `-5.14781353`

## Metrics

| Method | Split | RMSE | MAE | MSE | NASA score | R² |
|---|---|---:|---:|---:|---:|---:|
| weighted_average | val | 9.0651 | 6.5568 | 82.1762 | 6589.4423 | 0.9513 |
| weighted_average | test_raw | 13.5885 | 9.6277 | 184.6465 | 293.2910 | 0.8922 |
| weighted_average | test_clipped | 11.8464 | 8.0677 | 140.3362 | 250.2261 | 0.9085 |
| stacking | val | 8.8593 | 6.1541 | 78.4876 | 6161.0267 | 0.9535 |
| stacking | test_raw | 13.6982 | 9.8937 | 187.6411 | 294.3414 | 0.8905 |
| stacking | test_clipped | 12.0118 | 8.3337 | 144.2822 | 251.9128 | 0.9059 |

## Validation member error correlations

| Model | 01_lightgbm | 02_lstm | 03_bilstm_attention | 04_cnn1d | 05_transformer | 06_autoencoder | 07_cnn_transformer |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01_lightgbm | 1.0000 | 0.6907 | 0.7474 | 0.6456 | 0.7514 | 0.6632 | 0.7729 |
| 02_lstm | 0.6907 | 1.0000 | 0.7707 | 0.5751 | 0.6933 | 0.5998 | 0.7329 |
| 03_bilstm_attention | 0.7474 | 0.7707 | 1.0000 | 0.5852 | 0.8307 | 0.6043 | 0.8119 |
| 04_cnn1d | 0.6456 | 0.5751 | 0.5852 | 1.0000 | 0.4798 | 0.7055 | 0.7137 |
| 05_transformer | 0.7514 | 0.6933 | 0.8307 | 0.4798 | 1.0000 | 0.5759 | 0.7370 |
| 06_autoencoder | 0.6632 | 0.5998 | 0.6043 | 0.7055 | 0.5759 | 1.0000 | 0.6712 |
| 07_cnn_transformer | 0.7729 | 0.7329 | 0.8119 | 0.7137 | 0.7370 | 0.6712 | 1.0000 |
