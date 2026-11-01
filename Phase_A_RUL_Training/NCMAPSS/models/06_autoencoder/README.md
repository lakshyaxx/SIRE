# 06 - Sequence autoencoder + RUL head (NCMAPSS)

**Role:** Health indicator, per-sensor drift and degradation onset (the lead-up signal), plus an RUL estimate.
**Status:** not trained yet (update `STATUS.md` when done)

Use this file in one of two ways: paste the prompt below into Codex, or, once Codex has read Phase A, just say `train 06_autoencoder on DS01`.

## Codex prompt
```text
TASK: build, train, evaluate and compare the model `06_autoencoder` for the NCMAPSS track (SIRE Phase A). Then stop.

READ FIRST, in this order:
1. AGENTS.md
2. Phase_A_RUL_Training/README.md  (section 6: metrics, deep-model recipe, output contract, reporting)
3. Phase_A_RUL_Training/NCMAPSS/README.md  (the binding data protocol)
4. Phase_A_RUL_Training/NCMAPSS/common/  (shared code: reuse it, do not duplicate it)

PRECONDITION: 01_lightgbm has been trained on this dataset (its rows exist in results/comparison.csv), so there is a baseline to compare with. If it is not true, stop and tell me what is missing.

MODEL SPEC
GOAL
(1) A health indicator and a per-sensor drift signal learnt ONLY from healthy behaviour: this is the "something has been going wrong for a while" signal that later phases use as evidence. (2) An RUL estimate that uses the learnt representation.

STAGE 1 - healthy autoencoder (unsupervised)
- Healthy training windows: CMAPSS = windows whose true RUL >= cap (the flat part of the piecewise-linear target). NCMAPSS = windows with hs = 1 (health-state flag in the auxiliary array); if hs is not available, the first 30% of each unit's life. Document which rule was used.
- Model: LSTM encoder (hidden 64, 2 layers) -> latent vector (dim 16) -> LSTM decoder that reconstructs the whole window. Loss: MSE per channel. Early stopping on the reconstruction loss of healthy validation windows.
- For every window of every unit compute the per-channel reconstruction error; normalise each channel's error with the mean/std of the healthy validation windows (z-score); health indicator HI = mean of the channel z-scores.
- Onset detection: first step where HI stays above healthy mean + 3 std for 5 consecutive steps -> onset_step per unit (cycle or flight cycle). Report the share of test units with a detected onset and the median lead time between onset and failure.
- Quality of HI as a prognostic signal: Spearman correlation with true RUL, monotonicity and trendability (define each exactly in the code docstring).

STAGE 2 - RUL head
- Freeze the encoder and train an MLP head on [latent, HI] -> RUL (shared recipe) until early stopping; then unfreeze everything and fine-tune 10-20 epochs at lr 1e-4. Evaluate exactly like every other model.

SAVE
reconstruction_errors_test.csv (unit, step, channel, error, z), hi_test.csv, onset.csv, figures: HI vs time for 6 test units with onset marked, heat map of per-channel drift for 3 units.
predict.py returns rul plus hi, sensor_drift {channel: z at the latest step} and onset_step.

TRACK NOTES
- Input tensor (B, L, F): L = 50 downsampled steps (downsample factor 10), F = W + X_s channels. Never materialise all windows in memory: build them lazily from the per-unit arrays.
- Target: Y (RUL in flight cycles), uncapped unless the config says otherwise.
- Batch size 512; AMP allowed on CUDA; `max_windows_per_epoch` configurable (default: all; if an epoch takes more than about 10 minutes, subsample and say so in the report).
- Report window-level and flight-cycle-level metrics. With few development units the validation set is small and noisy; say so.

BUILD (inside Phase_A_RUL_Training/NCMAPSS/models/06_autoencoder/)
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
