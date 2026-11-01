# 08 - Ensemble (CMAPSS)

**Role:** Final candidate: combines the best members using validation data only.
**Status:** trained on FD001-FD004 with seed 42; both ensemble methods, validation selection, member-error correlations, and reports saved (2026-11-01). FD004 selected positive Ridge stacking (validation RMSE 13.7748 vs 13.7974 for weighted averaging; raw/clipped test RMSE 26.1007/14.1539). It beats LightGBM test RMSE by 3.93%/6.22% and the best earlier single models by 1.54%/4.43%. All seven members were available; positive Ridge coefficients are recorded in `outputs/FD004/seed_42/best_model.json`.

Use this file in one of two ways: paste the prompt below into Codex, or, once Codex has read Phase A, just say `train 08_ensemble on FD001`.

## Codex prompt
```text
TASK: build, train, evaluate and compare the model `08_ensemble` for the CMAPSS track (SIRE Phase A). Then stop.

READ FIRST, in this order:
1. AGENTS.md
2. Phase_A_RUL_Training/README.md  (section 6: metrics, deep-model recipe, output contract, reporting)
3. Phase_A_RUL_Training/CMAPSS/README.md  (the binding data protocol)
4. Phase_A_RUL_Training/CMAPSS/common/  (shared code: reuse it, do not duplicate it)

PRECONDITION: models 01-07 each have predictions_val.csv and predictions_test.csv for this dataset and seed. If it is not true, stop and tell me what is missing.

MODEL SPEC
INPUTS
The predictions_val.csv and predictions_test.csv saved by models 01-07 for the same dataset and seed. They share the same split, so rows align by unit and step. Check alignment explicitly and fail loudly if it is off.

METHODS (report both; the one with the lower VALIDATION RMSE is the official ensemble)
(a) Weighted average: non-negative weights that sum to 1, fitted on the validation predictions (scipy.optimize, minimise RMSE).
(b) Stacking: Ridge regression with positive=True on the validation predictions.

RULES
- Never fit weights on test data. Print the weights.
- Report whether the ensemble beats the best single model on test and by how much; report the pairwise correlation of member errors (diversity).
- predict.py of the ensemble loads the member predictors through their own predict.py and combines their outputs with the saved weights; it returns the members' individual predictions under "members".
- Models that did not train for a dataset are excluded and listed.

TRACK NOTES
- Input tensor (B, L, F): L = 30, F = kept sensors (plus standardised operating settings on the multi-condition subsets FD002 and FD004).
- Target: RUL clipped at 125 for training. Test is scored against the official RUL file (raw) and against the clipped RUL.
- Validation: 20% of the training engines, split by engine, early stopping on validation RMSE.
- FD001 first (fast), then FD002-FD004 with the same config. If a subset clearly needs a different setting, say so in the report and keep a separate config; never change settings silently.

BUILD (inside Phase_A_RUL_Training/CMAPSS/models/08_ensemble/)
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
