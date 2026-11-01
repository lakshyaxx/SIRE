# 06 - Sequence autoencoder + RUL head (CMAPSS)

**Role:** Health indicator, per-sensor drift and degradation onset (the lead-up signal), plus an RUL estimate.
**Status:** trained on FD001-FD004 with seed 42; health diagnostics, comparison and report saved (2026-11-01). On FD004, healthy reconstruction stopped at epoch 88 (best 73) and fine-tuning selected epoch 9. Validation RMSE was 15.7336 and raw/clipped test RMSE was 27.6947/15.9236. The clipped test RMSE is 5.51% worse than LightGBM (15.0921) and 7.52% worse than the best prior model, Transformer (14.8102); raw test RMSE is 1.94% worse than LightGBM and 4.48% worse than the prior best BiLSTM attention (26.5079). HI-RUL Spearman correlation was -0.3997, mean monotonicity 0.1189 and trendability 0.5885; onset was detected for 28/248 engines (11.3%, median lead 62.5 cycles).

Use this file in one of two ways: paste the prompt below into Codex, or, once Codex has read Phase A, just say `train 06_autoencoder on FD001`.

## Codex prompt
```text
TASK: build, train, evaluate and compare the model `06_autoencoder` for the CMAPSS track (SIRE Phase A). Then stop.

READ FIRST, in this order:
1. AGENTS.md
2. Phase_A_RUL_Training/README.md  (section 6: metrics, deep-model recipe, output contract, reporting)
3. Phase_A_RUL_Training/CMAPSS/README.md  (the binding data protocol)
4. Phase_A_RUL_Training/CMAPSS/common/  (shared code: reuse it, do not duplicate it)

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
- Input tensor (B, L, F): L = 30, F = kept sensors (plus standardised operating settings on the multi-condition subsets FD002 and FD004).
- Target: RUL clipped at 125 for training. Test is scored against the official RUL file (raw) and against the clipped RUL.
- Validation: 20% of the training engines, split by engine, early stopping on validation RMSE.
- FD001 first (fast), then FD002-FD004 with the same config. If a subset clearly needs a different setting, say so in the report and keep a separate config; never change settings silently.

BUILD (inside Phase_A_RUL_Training/CMAPSS/models/06_autoencoder/)
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
