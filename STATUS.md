# SIRE status

Update this file at the end of every step (Codex does it; you can edit it too).

## Phases
| Phase | Name | Status | Last update | Notes |
|---|---|---|---|---|
| A | RUL model training | in progress | 2026-11-01 | CMAPSS setup/audit and 8-model seed 42/43/44 results complete; existing weights were not retrained for uncertainty. `val_last` is used for selection and ensemble interval calibration. The LightGBM w50 ablation is complete. New LightGBM quantile models are fitted for every dataset/seed. Registry keeps its model shape and adds two uncertainty predictors per dataset; all 40 base/uncertainty registry loads passed from another cwd. The report includes interval metrics, an engine-level onset audit with four plots, and the full per-model breakdown in `CMAPSS/results/MODEL_RESULTS.md`. N-CMAPSS remains unstarted. |
| B | LLM integration | not started | - | |
| C | Knowledge base and RAG | not started | - | |
| D | Hypothesis engine | not started | - | |
| E | Vision | not started | - | |
| F | Frontend and voice | skeleton only | - | no frontend work until A-E are accepted |
| G | Final integration | not started | - | |

## Phase A detail
Cell values: `-` not started, a dataset id (FD001, DS01, ...) for partial progress, `done` when all datasets are finished.

| Track | Setup + audit | common/ + tests | 01 lightgbm | 02 lstm | 03 bilstm_attention | 04 cnn1d | 05 transformer | 06 autoencoder | 07 cnn_transformer | 08 ensemble | finalize |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CMAPSS | done | done | FD001, FD002, FD003, FD004 | FD001, FD002, FD003, FD004 | FD001, FD002, FD003, FD004 | FD001, FD002, FD003, FD004 | FD001, FD002, FD003, FD004 | FD001, FD002, FD003, FD004 | FD001, FD002, FD003, FD004 | FD001, FD002, FD003, FD004 | done |
| NCMAPSS | - | - | - | - | - | - | - | - | - | - | - |

## Log
Newest first. One line per step: date, step, one-sentence result.

- 2026-11-01, CMAPSS detailed results, wrote `CMAPSS/results/MODEL_RESULTS.md` with per-model, per-dataset all-window validation, `val_last`, raw/clipped test metrics, interval-predictor results, and onset summaries.
- 2026-11-01, CMAPSS uncertainty and onset audit, fitted LightGBM q10/q90 models for all 12 dataset/seed pairs; calibrated ensemble spread only on pooled `val_last` raw labels (80.0-80.3% validation coverage); evaluated both intervals on validation/test, audited all 2,121 autoencoder engine-seed rows, saved four six-engine HI/onset plots, verified all 40 registry prediction paths from another cwd, and passed 51 CMAPSS tests.
- 2026-11-01, CMAPSS finalization, completed seed 43/44 runs for models 04-08 without retraining seed 42; wrote multi-seed report and validation-selected registry, verified all 32 predictors from another cwd on raw test engine rows (0 failures), and passed 47 CMAPSS tests.
- 2026-11-01, CMAPSS finalization paused at user request; common `val_last` selection and tests added, LightGBM w50 ablation completed on FD001-FD004 with seeds 42/43/44, and seed 43/44 runs completed for models 01-03 on FD001-FD004 plus model 04 on FD001-FD003; 04 FD004 was interrupted and models 05-08 multi-seed runs have not started. Existing seed-42 base runs were reused.
- 2026-11-01, CMAPSS 08_ensemble on FD004, aligned all seven member prediction sets and selected positive Ridge stacking on validation (RMSE 13.7748 vs 13.7974 weighted average); stacking achieved raw/clipped test RMSE 26.1007/14.1539, improving on LightGBM by 3.93%/6.22% and the best prior single models by 1.54%/4.43%.
- 2026-11-01, CMAPSS 07_cnn_transformer on FD004, trained seed 42 on CUDA with early stopping at epoch 23 and best epoch 3; validation RMSE was 15.9568 and raw/clipped test RMSE was 28.7645/16.4140, worse than LightGBM and the best prior model on both test targets.
- 2026-11-01, CMAPSS 06_autoencoder on FD004, trained seed 42 on CUDA; healthy reconstruction stopped at epoch 88 (best 73), fine-tuned RUL head selected epoch 9, validation RMSE 15.7336 and raw/clipped test RMSE 27.6947/15.9236; HI-RUL Spearman was -0.3997 and onset was detected for 28/248 test engines (median lead 62.5 cycles).
- 2026-11-01, CMAPSS 05_transformer on FD004, trained seed 42 on CUDA with early stopping at epoch 27 and best epoch 7; validation RMSE was 15.4620 and raw/clipped test RMSE was 26.8034/14.8102; it improved on LightGBM test RMSEs but did not beat the best earlier model on raw test RMSE.
- 2026-11-01, CMAPSS 04_cnn1d on FD004, trained seed 42 on CUDA with early stopping at epoch 21 and best epoch 1; validation RMSE was 18.9970 and raw/clipped test RMSE was 31.6187/20.5117.
- 2026-11-01, CMAPSS 03_bilstm_attention on FD004, trained seed 42 on CUDA with early stopping at epoch 24 and best epoch 4; validation RMSE was 14.7967 and raw/clipped test RMSE was 26.5079/14.9517; saved attention for 20 test engines.
- 2026-11-01, CMAPSS 02_lstm on FD004, trained seed 42 on CUDA with early stopping at epoch 28 and best epoch 8; validation RMSE was 14.3755 and raw/clipped test RMSE was 26.9390/15.3934, beating the LightGBM validation baseline without tuning.
- 2026-11-01, CMAPSS 01_lightgbm on FD004, trained seed 42 on CPU using the supplied 249/248 train/test engine files; validation RMSE was 16.0283 and raw/clipped test RMSE was 27.1676/15.0921; 11 test engines required window padding.
- 2026-11-01, CMAPSS 08_ensemble on FD003, validation-selected positive Ridge stacking of all seven aligned members; validation RMSE was 8.7608 and raw/clipped test RMSE was 14.6006/13.0145; it beat LightGBM but not the best single-model test scores.
- 2026-11-01, CMAPSS 07_cnn_transformer on FD003, trained seed 42 on CUDA with early stopping at epoch 27 and best epoch 7; validation RMSE was 11.6075 and raw/clipped test RMSE was 14.6430/13.4334.
- 2026-11-01, CMAPSS 06_autoencoder on FD003, trained seed 42 on CUDA; fine-tune epoch 6 gave validation RMSE 13.9403 and raw/clipped test RMSE 18.6948/17.5862; onset detected for 45/100 test engines (median lead 136 cycles), with test HI Spearman correlation -0.1638 to RUL.
- 2026-11-01, CMAPSS 05_transformer on FD003, trained seed 42 on CUDA with early stopping at epoch 31 and best epoch 11; validation RMSE was 10.2182 and raw/clipped test RMSE was 13.8374/12.1168.
- 2026-11-01, CMAPSS 04_cnn1d on FD003, trained seed 42 on CUDA with early stopping at epoch 27 and best epoch 7; validation RMSE was 14.2167 and raw/clipped test RMSE was 17.4783/15.4519.
- 2026-11-01, CMAPSS 03_bilstm_attention on FD003, trained seed 42 on CUDA with early stopping at epoch 37 and best epoch 17; validation RMSE was 10.2821 and raw/clipped test RMSE was 13.8855/12.5517; saved attention for 20 test engines.
- 2026-11-01, CMAPSS 02_lstm on FD003, trained seed 42 on CUDA with early stopping at epoch 30 and best epoch 10; validation RMSE was 9.3052 and raw/clipped test RMSE was 15.8650/14.1417, beating the LightGBM validation baseline without tuning.
- 2026-11-01, CMAPSS 01_lightgbm on FD003, trained seed 42 on CPU (LightGBM wheel has no GPU backend); validation RMSE was 11.6036 and raw/clipped test RMSE was 14.7455/13.3093.
- 2026-11-01, CMAPSS 08_ensemble on FD002, validation-selected positive Ridge stacking of all seven aligned members; validation RMSE was 12.5383 and raw/clipped test RMSE was 25.6374/12.8469, improving on the best prior single model by 1.86%/4.64%.
- 2026-11-01, CMAPSS 07_cnn_transformer on FD002, trained seed 42 on CUDA with early stopping at epoch 23 and best epoch 3; validation RMSE was 16.6680 and raw/clipped test RMSE was 27.2984/15.1645.
- 2026-11-01, CMAPSS 06_autoencoder on FD002, trained seed 42 on CUDA; fine-tune epoch 15 gave validation RMSE 15.2970 and raw/clipped test RMSE 26.1241/13.4713; detected onset for 236/259 engines (91.1%), with median lead 178.5 cycles.
- 2026-11-01, CMAPSS 05_transformer on FD002, trained seed 42 on CUDA with early stopping at epoch 29 and best epoch 9; validation RMSE was 13.9538 and raw/clipped test RMSE was 27.0174/14.2748.
- 2026-11-01, CMAPSS 04_cnn1d on FD002, trained seed 42 on CUDA with early stopping at epoch 45 and best epoch 25; validation RMSE was 18.9450 and raw/clipped test RMSE was 30.7230/18.4355.
- 2026-11-01, CMAPSS 03_bilstm_attention on FD002, trained seed 42 on CUDA with early stopping at epoch 28 and best epoch 8; validation RMSE was 14.7915 and raw/clipped test RMSE was 26.7921/14.5262; saved attention for 20 test engines.
- 2026-11-01, CMAPSS 02_lstm on FD002, trained seed 42 on CUDA and early-stopped at epoch 24 (best epoch 4); validation RMSE was 12.9338 and raw/clipped test RMSE was 26.5419/13.7641.
- 2026-11-01, CMAPSS 01_lightgbm on FD002, trained seed 42 on CPU (LightGBM wheel has no GPU backend); validation RMSE was 14.7114 and raw/clipped test RMSE was 26.3253/13.4897; FD002 preprocessing dtype and predictor cluster-input dtype issues were fixed and verified.
- 2026-11-01, CMAPSS 08_ensemble on FD001, fit weighted-average and positive-Ridge blends using validation predictions; weighted average won validation RMSE (10.5631) and achieved raw/clipped test RMSE 14.1637/12.7823, beating the best single-model test RMSE by 2.99%/5.09%.
- 2026-11-01, CMAPSS 07_cnn_transformer on FD001, trained seed 42 on CUDA with early stopping at epoch 29 and best epoch 9; validation RMSE was 15.2646 and raw/clipped test RMSE was 17.1676/15.3147.
- 2026-11-01, CMAPSS 06_autoencoder on FD001, trained seed 42 on CUDA with healthy-only reconstruction and frozen-head/fine-tune stages; best fine-tune epoch 9 gave validation RMSE 16.5216 and raw/clipped test RMSE 17.5663/16.4597; detected onset for 43/100 test engines (median lead 71 cycles).
- 2026-11-01, CMAPSS 05_transformer on FD001, trained seed 42 on CUDA for 36 epochs (best epoch 16); validation RMSE was 11.5094 and raw/clipped test RMSE was 15.1369/13.9698; all 37 CMAPSS tests passed and the cwd-independent predictor returned a finite prediction.
- 2026-11-01, CMAPSS 04_cnn1d on FD001, trained seed 42 on CUDA with early stopping at epoch 33 and best epoch 13; validation RMSE was 17.7455 and raw/clipped test RMSE was 18.6904/17.2467.
- 2026-11-01, CMAPSS 03_bilstm_attention on FD001, trained seed 42 on CUDA with early stopping at epoch 34 and best epoch 14; validation RMSE was 12.7547 and raw/clipped test RMSE was 15.0402/13.9787; saved attention for 20 test engines.
- 2026-11-01, CMAPSS 02_lstm on FD001, compared seven validation-only candidates; selected 128 hidden units, two layers, dropout 0.3 and window 50. Final seed-42 CUDA run stopped at epoch 31 (best 11), with validation RMSE 11.3536 and raw/clipped test RMSE 15.5393/14.1498.
- 2026-11-01, CMAPSS common (Step 1), implemented the shared utilities and tests; 24 tests passed and the FD001 demo produced 16,779 training and 3,852 validation windows with an 80/20 engine split.
- 2026-11-01, CMAPSS 01_lightgbm on FD001, trained seed 42 with early stopping at 170 best iterations; validation RMSE was 12.6049 and raw/clipped test RMSE was 14.6009/13.4675.
- 2026-11-01, CMAPSS setup (Step 0), installed the pinned CUDA environment and audited all four subsets; after the FD004 249/248 count deviation was reported, the user directed work to start using the supplied files.
- 2026-10-31, CMAPSS setup (Step 0), created the Phase A virtual environment and pinned requirements; GPU detected; data audit initially blocked because required C-MAPSS files were absent and the CUDA PyTorch wheel download was interrupted before installation.
