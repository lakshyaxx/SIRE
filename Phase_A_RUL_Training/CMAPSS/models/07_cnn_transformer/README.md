# 07 - 1D-CNN + Transformer (CMAPSS)

**Role:** Hybrid: local features first, global attention second.
**Status:** trained on FD001-FD004 with seed 42; comparison and report updated (2026-11-01). On FD004, training stopped at epoch 23 and selected epoch 3: validation RMSE 15.9568, raw/clipped test RMSE 28.7645/16.4140. Validation RMSE is 0.45% better than LightGBM, but raw/clipped test RMSE are 5.88%/8.76% worse than LightGBM and 8.51%/10.83% worse than the prior best models (BiLSTM attention raw; Transformer clipped). Validation performance peaked early and deteriorated during continued training.

Use this file in one of two ways: paste the prompt below into Codex, or, once Codex has read Phase A, just say `train 07_cnn_transformer on FD001`.

## Codex prompt
```text
TASK: build, train, evaluate and compare the model `07_cnn_transformer` for the CMAPSS track (SIRE Phase A). Then stop.

READ FIRST, in this order:
1. AGENTS.md
2. Phase_A_RUL_Training/README.md  (section 6: metrics, deep-model recipe, output contract, reporting)
3. Phase_A_RUL_Training/CMAPSS/README.md  (the binding data protocol)
4. Phase_A_RUL_Training/CMAPSS/common/  (shared code: reuse it, do not duplicate it)

PRECONDITION: 01_lightgbm has been trained on this dataset (its rows exist in results/comparison.csv), so there is a baseline to compare with. If it is not true, stop and tell me what is missing.

MODEL SPEC
ARCHITECTURE
Input (B, L, F) -> two Conv1d blocks (F -> 64 -> 64, k=5, padding 2, BatchNorm, ReLU; sequence length preserved) -> permute to (B, L, 64) -> + sinusoidal positional encoding -> TransformerEncoder (2 layers, d_model 64, 4 heads, feed-forward 128, dropout 0.1, GELU, norm_first=True) -> concat(mean over time, last time step) = 128 -> Linear(128, 64) -> ReLU -> Dropout(0.2) -> Linear(64, 1).
Recipe as model 05 (lr 5e-4 with 5 warm-up epochs).

TRACK NOTES
- Input tensor (B, L, F): L = 30, F = kept sensors (plus standardised operating settings on the multi-condition subsets FD002 and FD004).
- Target: RUL clipped at 125 for training. Test is scored against the official RUL file (raw) and against the clipped RUL.
- Validation: 20% of the training engines, split by engine, early stopping on validation RMSE.
- FD001 first (fast), then FD002-FD004 with the same config. If a subset clearly needs a different setting, say so in the report and keep a separate config; never change settings silently.

BUILD (inside Phase_A_RUL_Training/CMAPSS/models/07_cnn_transformer/)
- config.yaml: every hyperparameter above. It is the single source of truth; train.py writes the config actually used next to the outputs.
- model.py: the model definition.
- train.py: CLI with --dataset (FD001 | FD002 | FD003 | FD004 | all), --seed, --seeds (several), --config, --device, --epochs (override). It must use common/ for data, splits, windows, metrics, early stopping, plots and reporting.
- predict.py: load_model(dataset, seed=None) -> Predictor with predict_rul(history_dataframe) -> dict, exactly as in Phase A README 6.3. It must work on raw sensor data (it loads the saved preprocessor itself), must not depend on the working directory, and must be importable by file path from another phase.
- outputs/<DATASET>/seed_<n>/: weights, config_used.yaml, metrics.json, predictions_val.csv, predictions_test.csv, history.csv (deep models), figures/.

RUN
1. Smoke test: python train.py --dataset FD001 --seed 42 --epochs 2 (deep models) and confirm every output file is written.
2. Real run: python train.py --dataset FD001 --seed 42. Other datasets only when I say "on all".
3. Final numbers only when I say finalize: --seeds 42 43 44.

AFTER TRAINING: do items a-e of Phase A README 6.6 (comparison.csv, REPORT.md, one table with deltas vs the baseline and vs the best so far, an honest verdict, files and commands, then STOP and wait for me).
```
