# 01 - LightGBM (CMAPSS)

**Role:** BASELINE. Every other model is compared against this one.
**Status:** trained on FD001-FD004 with seed 42; comparisons and reports updated (2026-11-01). FD004 used the audited supplied counts (249 train / 248 test); validation RMSE was 16.0283 and raw/clipped test RMSE was 27.1676/15.0921.

Use this file in one of two ways: paste the prompt below into Codex, or, once Codex has read Phase A, just say `train 01_lightgbm on FD001`.

## Codex prompt
```text
TASK: build, train, evaluate and compare the model `01_lightgbm` for the CMAPSS track (SIRE Phase A). Then stop.

READ FIRST, in this order:
1. AGENTS.md
2. Phase_A_RUL_Training/README.md  (section 6: metrics, deep-model recipe, output contract, reporting)
3. Phase_A_RUL_Training/CMAPSS/README.md  (the binding data protocol)
4. Phase_A_RUL_Training/CMAPSS/common/  (shared code: reuse it, do not duplicate it)

PRECONDITION: common/ is built and its tests pass, and results/data_audit.md exists for this dataset. If it is not true, stop and tell me what is missing.

MODEL SPEC
ARCHITECTURE
LightGBM gradient-boosted trees (regression) on engineered window features. This is the baseline: make it clean and solid, but untuned by default.

FEATURES (common/features.py; computed only from the same L-step window the deep models see, so the comparison is fair)
For every kept channel: last value, window mean, std, min, max, linear-regression slope over the window, last minus first, and (mean of the last 5 steps) minus (window mean). Plus the operating-condition id on multi-condition subsets. No feature may use data after the window end or any target information. Extended history features (whole-history rolling statistics, offset from the unit's early baseline) are allowed only as a separately named ablation `--extended_features`.

TRAINING
objective regression (L2), metric rmse, learning_rate 0.03, num_leaves 31, min_data_in_leaf 20, feature_fraction 0.7, bagging_fraction 0.8, bagging_freq 1, lambda_l2 1.0, n_estimators 5000 with early stopping (200 rounds) on validation RMSE, seed from the CLI. The CMAPSS target is RUL clipped at the cap.
Optional `--tune`: Optuna, 40 trials, objective = validation RMSE only; search num_leaves 15-127, min_data_in_leaf 5-100, feature_fraction 0.5-1.0, lambda_l2 1e-3 to 10 (log), learning_rate 0.01-0.1 (log). Save the best params to config_tuned.yaml and report the result as a separate model `01_lightgbm_tuned`. The untuned run stays the official baseline.

EXPLAINABILITY (used by Phases B and D)
- feature_importance.csv (gain) and top_contributors.csv: mean absolute per-channel contribution over the test set, computed with booster.predict(X, pred_contrib=True) (LightGBM's built-in SHAP-style values, no extra dependency).
- predict.py also returns the top 5 contributing channels for the prediction it just made.

TRACK NOTES
- Input tensor (B, L, F): L = 30, F = kept sensors (plus standardised operating settings on the multi-condition subsets FD002 and FD004).
- Target: RUL clipped at 125 for training. Test is scored against the official RUL file (raw) and against the clipped RUL.
- Validation: 20% of the training engines, split by engine, early stopping on validation RMSE.
- FD001 first (fast), then FD002-FD004 with the same config. If a subset clearly needs a different setting, say so in the report and keep a separate config; never change settings silently.

BUILD (inside Phase_A_RUL_Training/CMAPSS/models/01_lightgbm/)
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
