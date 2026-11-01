# CMAPSS track - protocol

Binding for every model in this track. Where the real data contradicts an expectation below, Codex reports it in `results/data_audit.md` and asks before deviating.

## 1. Data (files go in `data/`)
`train_FD00X.txt`, `test_FD00X.txt`, `RUL_FD00X.txt` for X = 1..4 (12 files) plus NASA's `readme.txt` and `Damage Propagation Modeling.pdf`.

Layout: whitespace-separated, no header, 26 columns = unit, cycle, op1, op2, op3, s1..s21. Rows end with trailing whitespace, so parse with `sep=r"\s+"`, `header=None` and drop empty trailing columns.

Expected sizes (verify and report differences):

| Subset | Operating conditions | Fault modes | Train engines | Test engines |
|---|---|---|---|---|
| FD001 | 1 | 1 (HPC degradation) | 100 | 100 |
| FD002 | 6 | 1 (HPC degradation) | 260 | 259 |
| FD003 | 1 | 2 (HPC + fan) | 100 | 100 |
| FD004 | 6 | 2 (HPC + fan) | 248 | 249 |

## 2. Protocol
1. **Labels.** Training RUL = max_cycle(unit) - cycle. Training target = min(RUL, cap), cap = 125 (config, per dataset). Keep the raw RUL too.
2. **Sensors.** Drop sensors that are exactly constant in the training split of that subset (find them programmatically and log them). Keep the others.
3. **Normalisation.** Fit on the training split only. Single-condition subsets: standardise per sensor. Multi-condition subsets (FD002, FD004): cluster the three operating settings (KMeans, k = number of conditions, verified on the data), then standardise each sensor within its cluster using training statistics. Include the standardised operating settings as inputs on multi-condition subsets only.
4. **Windows.** Length L = 30, stride 1, one window per cycle ending at that cycle. Cycles with fewer than L previous observations are left-padded by repeating the first observation (also at test time); count and report how many test engines need padding. Target = clipped RUL at the window's last cycle.
5. **Splits.** 80/20 train/validation by engine, seed 42, written to `results/splits.json` and reused by every model. Test = the official test set, last window per engine, truth from `RUL_FD00X.txt` (row i = engine i).
6. **Evaluation.** Report the original all-window validation metrics and the finalization-only `val_last` metrics. `val_last` selects the last validation endpoint plus five fixed-seed random truncation endpoints per validation engine; it is used for cross-model and registry selection. Test remains the last window per engine, scored against both `raw` and `clipped` targets. Never use test metrics to select a model.
7. **Fairness.** Every model sees the same windows, splits and preprocessing. LightGBM gets features computed from the same window.

## 3. Defaults (`common/config.py`)
| Setting | Default |
|---|---|
| rul_cap | 125 |
| window_length | 30 |
| stride | 1 |
| val_fraction (by engine) | 0.2 |
| seed | 42 |
| batch_size (deep) | 256 |
| device | cuda if available else cpu |

## 4. Track prompt (use when you start a fresh Codex session on this track)
```text
TRACK BRIEFING: CMAPSS (SIRE Phase A). Read AGENTS.md, Phase_A_RUL_Training/README.md (sections 6 and 7) and this README. The protocol above is binding. My commands: `setup cmapss`, `build common cmapss`, `train <model> on <FD001|FD002|FD003|FD004|all>`, `compare cmapss`, `finalize cmapss`. Do one command at a time, report with real numbers, then stop. Start by confirming what you read and wait for `setup cmapss`.
```

## 5. Prediction intervals and onset-quality audit
`08_ensemble` returns member prediction spread and an 80% interval. One spread scale is calibrated per dataset using pooled seed 42/43/44 `val_last` raw-RUL residuals; test labels are evaluation-only. `01_lightgbm_quantile` fits alpha 0.1 and 0.9 LightGBM models using the baseline feature schema and the fixed engine split. Existing model weights are not retrained.

```powershell
python models/01_lightgbm_quantile/train.py --dataset all --seeds 42 43 44
python evaluate_uncertainty.py
python check_onset_quality.py
python verify_registry.py
python validate_finalization.py
```

`results/uncertainty_metrics.csv` reports coverage, mean width, and Pearson correlation between width and absolute error for `val_last` and both test target flavors. `results/onset_quality_by_engine.csv` records the true RUL at each first onset; only onsets after true RUL drops below the 125-cycle cap count as detections and contribute lead time. Six seed-42 HI/onset panels per dataset are written under `results/figures/onset_quality/`.
