# NCMAPSS common/ - shared code (Step 1)

Everything every model needs, written once and tested. Memory-safe by design: data stays per unit on disk or in float32 arrays, windows are generated lazily.

## Step 1 prompt (`build common ncmapss`)
```text
STEP 1 - build common ncmapss (SIRE Phase A). Precondition: Step 0 done and results/data_audit.md exists. Implement the modules below in Phase_A_RUL_Training/NCMAPSS/common/ exactly to the protocol in NCMAPSS/README.md, then write pytest tests in NCMAPSS/tests/ and make them all pass. Real code, no stubs. Tests must run on a tiny real slice of the data (a few units/flights), not on fabricated arrays, plus synthetic arrays only for pure-function unit tests (metrics, windowing shapes).

MODULES
config.py          defaults (downsample 10, L 50, stride 10, batch 512, seed 42) and the list of sub-datasets found in data/
h5_loader.py       lazy per-unit access to dev/test arrays, decoded channel names, float32, optional cache of the downsampled series per unit in results/artifacts/<DATASET>/
preprocess.py      channel selection (W + X_s), downsampling inside flight cycles, StandardScaler fitted on training units only; save/load
splits.py          unit-level train/validation split written to ../results/splits.json
windows.py         lazy window index (unit, cycle, end position) and a torch Dataset that builds windows on demand; no window crosses a unit boundary and, by default, a flight-cycle boundary
features.py        engineered window features for LightGBM (spec in models/01_lightgbm/README.md)
aggregate.py       window predictions -> flight-cycle predictions (mean per flight cycle) and per-unit summaries
metrics.py         mse, rmse, mae, r2, nasa_score, nasa_score_mean
evaluate.py        one evaluation routine for all models: val window, test window, test flight_cycle, per-unit errors
train_utils.py     seeding, device selection, early stopping, the shared deep-model trainer (Phase A README 6.2) with max_windows_per_epoch, optional AMP, checkpointing, history.csv
plots.py           loss curves, predicted vs true, RUL trace per test unit, error by RUL band
report.py          append/replace rows in results/comparison.csv and regenerate results/REPORT.md
registry.py        write/read model_registry.json
predictor_base.py  base class for predict.py: takes 1 Hz rows of one unit, returns the dict contract of Phase A README 6.3 with a per-cycle trace
_bootstrap.py      makes `common` importable from model folders whose names start with a digit by adding the track root to sys.path. Do NOT pip-install `common` as a top-level package (the two tracks would collide).

TESTS (NCMAPSS/tests/)
test_loader.py, test_windows.py (shapes, no boundary crossing, laziness: peak memory stays bounded), test_splits.py (no unit in both splits), test_preprocess.py (scaler statistics from training units only), test_metrics.py (incl. NASA score), test_aggregate.py, test_report.py.

DONE WHEN: pytest passes, a short demo prints channel names, number of windows and one window's shape for the first sub-dataset, and peak RAM stays within the machine's limits. Update STATUS.md, report with real output, then STOP.
```
