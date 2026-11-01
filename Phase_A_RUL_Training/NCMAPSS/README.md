# NCMAPSS track - protocol

Binding for every model in this track. Where the real files contradict an expectation below, Codex reports it in `results/data_audit.md` and asks before deviating.

## 1. Data (files go in `data/`)
The downloaded N-CMAPSS HDF5 file(s), for example `N-CMAPSS_DS01-005.h5`. Each file is one sub-dataset (DS01, DS02, ...) holding flight-by-flight run-to-failure data sampled at 1 Hz. The files are large (millions of rows): use float32, read per unit, never build all windows in memory.

Expected HDF5 contents (**verify with h5py, do not assume**): arrays `W_dev, X_s_dev, X_v_dev, T_dev, Y_dev, A_dev` for the development (training) units and the same with the `_test` suffix for the test units, plus name arrays `W_var, X_s_var, X_v_var, T_var, A_var` (bytes; decode them).

| Array | Meaning | Used as model input? |
|---|---|---|
| W | operating conditions (scenario descriptors) | yes |
| X_s | measured sensor signals | yes |
| X_v | virtual sensors (model-estimated, not measurable on a real engine) | no (only as a clearly flagged ablation `--use_virtual_sensors`) |
| T | health parameters (ground truth of the degradation, not observable) | never |
| Y | RUL in flight cycles | label only |
| A | auxiliary: unit id, flight cycle, flight class Fc, health-state flag hs | ids and cycle only; `hs` only to pick healthy windows for model 06 |

## 2. Protocol
1. **Inputs.** W + X_s only. The input channel list is read from the name arrays and logged.
2. **Downsampling.** Keep every 10th sample inside each flight cycle (config `downsample: 10`, 1 Hz -> 0.1 Hz).
3. **Windows.** Length L = 50 downsampled steps, stride 10 for training windows (stride 1 for the final test pass if memory allows, otherwise stride 10 and say so). Windows never cross unit boundaries and by default stay inside one flight cycle (`cross_cycle_windows: false`). Target = Y at the window's last sample.
4. **Scaling.** StandardScaler fitted on the downsampled training units only; saved to `results/artifacts/<DATASET>/`.
5. **Splits.** Development units are split into train/validation by unit (about 20% of units, at least one, chosen with seed 42, written to `results/splits.json`). The official test units are never touched until final evaluation. With few development units validation is noisy; say so in every report.
6. **Target.** Y uncapped by default; a cap is a config option and must be documented if used (`rul_cap: null`).
7. **Evaluation.** Phase A README 6.1: `level=window` and `level=flight_cycle` (mean of window predictions inside a flight cycle vs that cycle's RUL); also report per-test-unit errors. Report `nasa_score` (sum) and `nasa_score_mean`.
8. **Fairness.** Every model sees the same windows, splits and preprocessing. LightGBM gets features computed from the same windows (stride 10).
9. **Predictor input.** `predict_rul(history)` takes the 1 Hz rows (W + X_s channel names as columns, plus a flight-cycle column) of one unit covering at least its latest flight cycle and returns the RUL (flight cycles) for the latest cycle plus a per-cycle trace.

## 3. Defaults (`common/config.py`)
| Setting | Default |
|---|---|
| downsample | 10 |
| window_length | 50 |
| stride (train) | 10 |
| cross_cycle_windows | false |
| val units | ~20% of development units, min 1 |
| rul_cap | null |
| seed | 42 |
| batch_size (deep) | 512 |
| device | cuda if available else cpu |

## 4. Track prompt (use when you start a fresh Codex session on this track)
```text
TRACK BRIEFING: NCMAPSS (SIRE Phase A). Read AGENTS.md, Phase_A_RUL_Training/README.md (sections 6 and 7) and this README. The protocol above is binding. My commands: `setup ncmapss`, `build common ncmapss`, `train <model> on <DS id|all>`, `compare ncmapss`, `finalize ncmapss`. Do one command at a time, report with real numbers, then stop. Memory is the main risk: stream per unit, float32, lazy windows. Start by confirming what you read and wait for `setup ncmapss`.
```
