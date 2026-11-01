# 05 - Transformer encoder (NCMAPSS)

**Role:** Global self-attention over the window.
**Status:** not trained yet (update `STATUS.md` when done)

Use this file in one of two ways: paste the prompt below into Codex, or, once Codex has read Phase A, just say `train 05_transformer on DS01`.

## Codex prompt
```text
TASK: build, train, evaluate and compare the model `05_transformer` for the NCMAPSS track (SIRE Phase A). Then stop.

READ FIRST, in this order:
1. AGENTS.md
2. Phase_A_RUL_Training/README.md  (section 6: metrics, deep-model recipe, output contract, reporting)
3. Phase_A_RUL_Training/NCMAPSS/README.md  (the binding data protocol)
4. Phase_A_RUL_Training/NCMAPSS/common/  (shared code: reuse it, do not duplicate it)

PRECONDITION: 01_lightgbm has been trained on this dataset (its rows exist in results/comparison.csv), so there is a baseline to compare with. If it is not true, stop and tell me what is missing.

MODEL SPEC
ARCHITECTURE
Input (B, L, F) -> Linear(F, 64) -> + sinusoidal positional encoding (max_len >= L) -> TransformerEncoder (3 layers, d_model 64, 4 heads, feed-forward 128, dropout 0.1, GELU, norm_first=True) -> concat(mean over time, last time step) = 128 -> Linear(128, 64) -> ReLU -> Dropout(0.2) -> Linear(64, 1).
Recipe override: lr 5e-4 with 5 warm-up epochs (linear) then ReduceLROnPlateau; everything else as the shared deep-model recipe (Phase A README 6.2).

TRACK NOTES
- Input tensor (B, L, F): L = 50 downsampled steps (downsample factor 10), F = W + X_s channels. Never materialise all windows in memory: build them lazily from the per-unit arrays.
- Target: Y (RUL in flight cycles), uncapped unless the config says otherwise.
- Batch size 512; AMP allowed on CUDA; `max_windows_per_epoch` configurable (default: all; if an epoch takes more than about 10 minutes, subsample and say so in the report).
- Report window-level and flight-cycle-level metrics. With few development units the validation set is small and noisy; say so.

BUILD (inside Phase_A_RUL_Training/NCMAPSS/models/05_transformer/)
- config.yaml: every hyperparameter above. It is the single source of truth; train.py writes the config actually used next to the outputs.
- model.py: the model definition.
- train.py: CLI with --dataset (the sub-dataset id read from each .h5 file name (for example DS01) | all), --seed, --seeds (several), --config, --device, --epochs (override). It must use common/ for data, splits, windows, metrics, early stopping, plots and reporting.
- predict.py: load_model(dataset, seed=None) -> Predictor with predict_rul(history_dataframe) -> dict, exactly as in Phase A README 6.3. It must work on raw sensor data (it loads the saved preprocessor itself), must not depend on the working directory, and must be importable by file path from another phase.
- outputs/<DATASET>/seed_<n>/: weights, config_used.yaml, metrics.json, predictions_val.csv, predictions_test.csv, history.csv (deep models), figures/.

RUN
1. Smoke test: python train.py --dataset DS01 --seed 42 --epochs 2 (deep models) and confirm every output file is written.
2. Real run: python train.py --dataset DS01 --seed 42. Other datasets only when I say "on all".
3. Final numbers only when I say finalize: --seeds 42 43 44.

AFTER TRAINING: do items a-e of Phase A README 6.6 (comparison.csv, REPORT.md, one table with deltas vs the baseline and vs the best so far, an honest verdict, files and commands, then STOP and wait for me).
```
