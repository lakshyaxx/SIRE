# 02 - LSTM (CMAPSS)

**Role:** First sequence model. Shows what recurrence adds over hand-built window features.
**Status:** trained on FD001-FD004 with seed 42. FD001 validation-only tuning selected 128 hidden units, two layers, dropout 0.3, and a 50-cycle window; the same config was used on FD002-FD004. FD004 validation RMSE was 14.3755; raw/clipped test RMSE was 26.9390/15.3934. See the per-dataset outputs and `CMAPSS/results/REPORT.md`.

Use this file in one of two ways: paste the prompt below into Codex, or, once Codex has read Phase A, just say `train 02_lstm on FD001`.

## Codex prompt
```text
TASK: build, train, evaluate and compare the model `02_lstm` for the CMAPSS track (SIRE Phase A). Then stop.

READ FIRST, in this order:
1. AGENTS.md
2. Phase_A_RUL_Training/README.md  (section 6: metrics, deep-model recipe, output contract, reporting)
3. Phase_A_RUL_Training/CMAPSS/README.md  (the binding data protocol)
4. Phase_A_RUL_Training/CMAPSS/common/  (shared code: reuse it, do not duplicate it)

PRECONDITION: 01_lightgbm has been trained on this dataset (its rows exist in results/comparison.csv), so there is a baseline to compare with. If it is not true, stop and tell me what is missing.

MODEL SPEC
ARCHITECTURE
Input (B, L, F) -> LSTM(hidden 64, 2 layers, dropout 0.3, batch_first) -> hidden state at the last step -> Linear(64, 32) -> ReLU -> Dropout(0.2) -> Linear(32, 1).
Target scaled by the cap (CMAPSS) or by the maximum training RUL (NCMAPSS) and un-scaled at inference. Loss MSE. Shared deep-model recipe (Phase A README 6.2).
If it underperforms the baseline, try (validation only, every trial logged): hidden 128, 1-3 layers, dropout 0.2-0.4, window 30/40/50.

TRACK NOTES
- Input tensor (B, L, F): L = 30, F = kept sensors (plus standardised operating settings on the multi-condition subsets FD002 and FD004).
- Target: RUL clipped at 125 for training. Test is scored against the official RUL file (raw) and against the clipped RUL.
- Validation: 20% of the training engines, split by engine, early stopping on validation RMSE.
- FD001 first (fast), then FD002-FD004 with the same config. If a subset clearly needs a different setting, say so in the report and keep a separate config; never change settings silently.

BUILD (inside Phase_A_RUL_Training/CMAPSS/models/02_lstm/)
- config.yaml: every hyperparameter above. It is the single source of truth; train.py writes the config actually used next to the outputs.
- model.py: the model definition.
- train.py: CLI with --dataset (FD001 | FD002 | FD003 | FD004 | all), --seed, --seeds (several), --config, --device, --epochs (override). It must use common/ for data, splits, windows, metrics, early stopping, plots and reporting.
- predict.py: load_model(dataset, seed=None) -> Predictor with predict_rul(history_dataframe) -> dict, exactly as in Phase A README 6.3. It must work on raw sensor data (it loads the saved preprocessor itself), must not depend on the working directory, and must be importable by file path from another phase.
- outputs/<DATASET>/seed_<n>/: weights, config_used.yaml, metrics.json, predictions_val.csv, predictions_test.csv, history.csv (deep models), figures/.

RUN
1. Smoke test: python train.py --dataset FD001 --seed 42 --epochs 2 (deep models) and confirm every output file is written.
2. Real run: python train.py --dataset FD001 --seed 42. Other datasets only when I say "on all".
3. Final numbers only when I say finalize: --seeds 42 43 44.

If the default configuration underperforms LightGBM on validation RMSE, pass `--tune` for the logged validation-only sweep. It requires a previous default run, writes `outputs/<DATASET>/seed_<n>/tuning_log.csv`, selects by validation RMSE, updates `config.yaml`, and performs a final fit/evaluation.

AFTER TRAINING: do items a-e of Phase A README 6.6 (comparison.csv, REPORT.md, one table with deltas vs the baseline and vs the best so far, an honest verdict, files and commands, then STOP and wait for me).
```
