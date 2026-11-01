# 04 - 1D-CNN (CMAPSS)

**Role:** Fast local-pattern model. Shows whether convolution alone is enough.
**Status:** trained on FD001-FD004 with seed 42; see `outputs/<DATASET>/seed_42/` and `CMAPSS/results/REPORT.md` for artifacts and comparisons. On FD004, best validation RMSE was 18.9970 (epoch 1); raw/clipped test RMSE was 31.6187/20.5117. On FD003, best validation RMSE was 14.2167 (epoch 7).

Use this file in one of two ways: paste the prompt below into Codex, or, once Codex has read Phase A, just say `train 04_cnn1d on FD001`.

## Codex prompt
```text
TASK: build, train, evaluate and compare the model `04_cnn1d` for the CMAPSS track (SIRE Phase A). Then stop.

READ FIRST, in this order:
1. AGENTS.md
2. Phase_A_RUL_Training/README.md  (section 6: metrics, deep-model recipe, output contract, reporting)
3. Phase_A_RUL_Training/CMAPSS/README.md  (the binding data protocol)
4. Phase_A_RUL_Training/CMAPSS/common/  (shared code: reuse it, do not duplicate it)

PRECONDITION: 01_lightgbm has been trained on this dataset (its rows exist in results/comparison.csv), so there is a baseline to compare with. If it is not true, stop and tell me what is missing.

MODEL SPEC
ARCHITECTURE
Input permuted to (B, F, L) -> Conv1d(F, 64, k=5, pad=2) + BatchNorm + ReLU -> Conv1d(64, 128, k=5, pad=2) + BatchNorm + ReLU + Dropout(0.2) -> Conv1d(128, 128, k=3, pad=1) + BatchNorm + ReLU -> concat(global average pool, global max pool) = 256 -> Linear(256, 64) -> ReLU -> Dropout(0.3) -> Linear(64, 1).
Shared deep-model recipe (Phase A README 6.2).

TRACK NOTES
- Input tensor (B, L, F): L = 30, F = kept sensors (plus standardised operating settings on the multi-condition subsets FD002 and FD004).
- Target: RUL clipped at 125 for training. Test is scored against the official RUL file (raw) and against the clipped RUL.
- Validation: 20% of the training engines, split by engine, early stopping on validation RMSE.
- FD001 first (fast), then FD002-FD004 with the same config. If a subset clearly needs a different setting, say so in the report and keep a separate config; never change settings silently.

BUILD (inside Phase_A_RUL_Training/CMAPSS/models/04_cnn1d/)
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
