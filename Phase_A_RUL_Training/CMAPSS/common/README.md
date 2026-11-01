# CMAPSS common/ - shared code (Step 1)

Everything every model needs, written once and tested. Models import from here; they never re-implement data handling or metrics.

## Step 1 prompt (`build common cmapss`)
```text
STEP 1 - build common cmapss (SIRE Phase A). Precondition: Step 0 done and results/data_audit.md exists. Implement the modules below in Phase_A_RUL_Training/CMAPSS/common/ exactly to the protocol in CMAPSS/README.md, then write pytest tests in CMAPSS/tests/ and make them all pass. Real code, no stubs.

MODULES
config.py          dataset registry (files, n_conditions) and defaults (cap 125, L 30, stride 1, val_fraction 0.2, seed 42)
data.py            parse train/test/RUL files, name columns, compute raw and clipped RUL, basic validation
preprocess.py      constant-sensor removal and condition-aware standardisation (KMeans on operating settings for multi-condition subsets), fitted on the training split only; save/load preprocessor.joblib in ../results/artifacts/<DATASET>/
splits.py          engine-level train/validation split written to ../results/splits.json and reloaded so every model uses the same one
windows.py         sliding windows with left padding, the test last-window builder, a torch Dataset
features.py        engineered window features for LightGBM (spec in models/01_lightgbm/README.md)
metrics.py         mse, rmse, mae, r2, nasa_score, nasa_score_mean
evaluate.py        one evaluation routine for all models: val, test raw, test clipped
train_utils.py     seeding, device selection, early stopping, the shared deep-model trainer (Phase A README 6.2), checkpointing, history.csv
plots.py           loss curves, predicted vs true, residual histogram, error by RUL band, worst-10 engines
report.py          append/replace rows in results/comparison.csv and regenerate results/REPORT.md (tables, deltas vs baseline and vs best so far, figures)
registry.py        write/read model_registry.json
val_last.py        deterministic selection of each validation engine's last endpoint plus five fixed-seed random truncations; final model ranking only uses validation metrics from these rows
predictor_base.py  base class for predict.py: loads the preprocessor, builds the window from raw history, returns the dict contract of Phase A README 6.3
_bootstrap.py      makes `common` importable from model folders whose names start with a digit by adding the track root to sys.path. Do NOT pip-install `common` as a top-level package (the two tracks would collide).

TESTS (CMAPSS/tests/)
test_parse.py (columns, trailing whitespace, row counts), test_windows.py (shapes, left padding, no future leakage), test_splits.py (no engine in both splits, deterministic), test_preprocess.py (statistics come from the training split only), test_metrics.py (hand-computed cases including the NASA score and its asymmetry), test_report.py (rows replaced, not duplicated), test_val_last.py (last endpoint, deterministic random points, short engines, metrics).

DONE WHEN: pytest passes, a 5-line demo prints the window tensor shape and split sizes for FD001, STATUS.md is updated. Report with real output, then STOP.
```
