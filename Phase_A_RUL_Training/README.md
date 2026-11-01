# Phase A - RUL Model Training (C-MAPSS + N-CMAPSS)

| | |
|---|---|
| Status | not started (tracked in `STATUS.md`) |
| Depends on | nothing, only the datasets |
| Feeds | Phase B (the models become LLM tools) and Phase D (RUL, drift and onset become evidence) |

## 1. What happens in this phase
We train Remaining-Useful-Life (RUL) models on NASA's two turbofan degradation datasets and compare them honestly. Two independent tracks, same protocol, same eight models:

- `CMAPSS/` - classic C-MAPSS, subsets FD001-FD004, one row per engine cycle.
- `NCMAPSS/` - N-CMAPSS, flight-by-flight data under realistic operating conditions.

Models are trained **one at a time**, always in this order, each in its own folder:

| # | Folder | Model | Role |
|---|---|---|---|
| 01 | `01_lightgbm` | LightGBM | BASELINE. Every other model is compared against this one. |
| 02 | `02_lstm` | LSTM | First sequence model. Shows what recurrence adds over hand-built window features. |
| 03 | `03_bilstm_attention` | BiLSTM + temporal attention | Bidirectional context inside the window plus an attention map you can inspect. |
| 04 | `04_cnn1d` | 1D-CNN | Fast local-pattern model. Shows whether convolution alone is enough. |
| 05 | `05_transformer` | Transformer encoder | Global self-attention over the window. |
| 06 | `06_autoencoder` | Sequence autoencoder + RUL head | Health indicator, per-sensor drift and degradation onset (the lead-up signal), plus an RUL estimate. |
| 07 | `07_cnn_transformer` | 1D-CNN + Transformer | Hybrid: local features first, global attention second. |
| 08 | `08_ensemble` | Ensemble | Final candidate: combines the best members using validation data only. |

After every model Codex must: train it, evaluate it (RMSE, MAE, MSE, NASA score, R2), compare it with the LightGBM baseline and every earlier model, give an honest verdict, then **stop and wait for you**.

Recommended rhythm: get the whole ladder (01 to 08) working on FD001 first because it is fast; then run each model on `all` subsets; then `finalize`. Do the same on N-CMAPSS, starting with one sub-dataset.

## 2. Folder map
```text
Phase_A_RUL_Training/
├── README.md   # master prompt + shared protocol (read this first)
├── CMAPSS/   # FD001-FD004
│   ├── README.md   # track protocol (binding) + track prompt
│   ├── data/   # put the dataset here
│   │   └── README.md   # expected files + Step 0 prompt (setup / audit)
│   ├── common/   # shared code, built in Step 1
│   │   └── README.md   # Step 1 prompt: modules to build
│   ├── models/   # one folder per model, trained one at a time
│   │   ├── 01_lightgbm/   # LightGBM
│   │   │   ├── README.md   # training prompt
│   │   │   └── outputs/   # weights, metrics, predictions, figures
│   │   ├── 02_lstm/   # LSTM
│   │   │   ├── README.md   # training prompt
│   │   │   └── outputs/   # weights, metrics, predictions, figures
│   │   ├── 03_bilstm_attention/   # BiLSTM + temporal attention
│   │   │   ├── README.md   # training prompt
│   │   │   └── outputs/   # weights, metrics, predictions, figures
│   │   ├── 04_cnn1d/   # 1D-CNN
│   │   │   ├── README.md   # training prompt
│   │   │   └── outputs/   # weights, metrics, predictions, figures
│   │   ├── 05_transformer/   # Transformer encoder
│   │   │   ├── README.md   # training prompt
│   │   │   └── outputs/   # weights, metrics, predictions, figures
│   │   ├── 06_autoencoder/   # Sequence autoencoder + RUL head
│   │   │   ├── README.md   # training prompt
│   │   │   └── outputs/   # weights, metrics, predictions, figures
│   │   ├── 07_cnn_transformer/   # 1D-CNN + Transformer
│   │   │   ├── README.md   # training prompt
│   │   │   └── outputs/   # weights, metrics, predictions, figures
│   │   └── 08_ensemble/   # Ensemble
│   │       ├── README.md   # training prompt
│   │       └── outputs/   # weights, metrics, predictions, figures
│   ├── results/   # comparison.csv, REPORT.md, figures, artifacts
│   │   └── README.md   # what is written here
│   └── tests/   # pytest tests for common/
└── NCMAPSS/   # identical layout, for the N-CMAPSS .h5 files
```
Each model folder holds its `README.md` (the training prompt) and an empty `outputs/`. Codex adds `config.yaml`, `model.py`, `train.py` and `predict.py` when you ask it to train that model. `requirements.txt` is created once, at the Phase A root, in Step 0.

## 3. Before you start
1. Put the datasets in `CMAPSS/data/` and `NCMAPSS/data/` (each folder's README lists the expected files).
2. Python 3.10+. An NVIDIA GPU is recommended for the deep models; Codex detects it and falls back to CPU with a warning.
3. Open the repository root (`SIRE/`) in VS Code so Codex can read `AGENTS.md`.

## 4. The Codex prompt (paste once at the start of Phase A)
```text
You are the lead ML engineer for SIRE, Phase A: Remaining-Useful-Life (RUL) model training on NASA C-MAPSS and N-CMAPSS.

WHY THIS PHASE EXISTS
SIRE diagnoses why a machine part failed and how it could have been prevented. Later, a local Qwen LLM agent will call the RUL models trained here as tools (Phase B) and a hypothesis engine will use their outputs as evidence (Phase D). So every model must be trained properly, evaluated honestly and saved so that it can be loaded later and called with raw sensor data.

HARD RULES
1. Real work only: no placeholders, no TODO stubs, no dummy or invented data, no hard-coded or estimated metrics. Every number you report must come from code you ran in this session.
2. Look before you build: inspect the real files in the track's data/ folder first. Never assume a schema.
3. No leakage: split by engine/unit (never by row); fit scalers, clusterers and feature statistics on the training split only; never tune on the test set; features may use only the present and the past.
4. Reproducible: seed 42 by default, one config.yaml per model, pinned requirements, identical splits for all models (results/splits.json).
5. Cross-platform code (Windows, macOS, Linux): pathlib, no shell-only scripts, DataLoader num_workers configurable (default 0).
6. Use CUDA when torch.cuda.is_available() (print the GPU name), otherwise CPU with a visible warning.
7. Stay inside Phase_A_RUL_Training/ (plus STATUS.md). One model per instruction, then STOP and wait for me.
8. If something blocks you (missing file, library failure, out of memory) say exactly what it is and offer options. Never fake your way around it.
9. Open-source tools only. Update STATUS.md after every completed step.

READ FIRST (every session): AGENTS.md, this README (sections 6 and 7), the track README (CMAPSS/README.md or NCMAPSS/README.md) and the README of the model I ask for.

WORKFLOW (I trigger each step with a short command)
Step 0  `setup <track>`: create .venv and a pinned requirements.txt (at the Phase A root, once), inspect the data, write <track>/results/data_audit.md and figures. Report anything that contradicts the track README. Details: <track>/data/README.md.
Step 1  `build common <track>`: implement <track>/common/ exactly as described in <track>/common/README.md, with pytest tests in <track>/tests/. All tests must pass.
Step 2  `train 01_lightgbm on <dataset|all>`: the baseline.
Steps 3-9  `train 02_lstm ...`, `03_bilstm_attention`, `04_cnn1d`, `05_transformer`, `06_autoencoder`, `07_cnn_transformer`, `08_ensemble`, always in this order.
Step 10  `finalize <track>`: run every model with 3 seeds (42, 43, 44) where not done yet, write the final results/REPORT.md (mean +- std), choose the best model per dataset on VALIDATION data, write model_registry.json. Ask me before adding optional prediction uncertainty (MC-dropout, quantile LightGBM, ensemble spread).
Other commands: `compare <track>` regenerates REPORT.md without training; `status` prints the STATUS.md summary.

AFTER EACH MODEL (mandatory, section 6.6)
a) Append rows to <track>/results/comparison.csv and regenerate results/REPORT.md.
b) Print one table: val and test RMSE/MAE/MSE/NASA/R2, delta vs baseline (%), delta vs best so far (%).
c) Give an honest verdict: better or worse than the baseline, by how much, whether the gap could be seed noise, one likely reason, one concrete next improvement.
d) List files created or changed and the exact commands you ran.
e) STOP.

Reply "Phase A ready" followed by a 6-line summary of what you will do in Step 0 and Step 1. Do not train anything yet. Wait for my first command.
```

## 5. How you drive Codex
```text
setup cmapss                       # Step 0: environment + data audit
build common cmapss                # Step 1: shared code + tests
train 01_lightgbm on FD001         # baseline on one subset
train 02_lstm on FD001             # next model, compared with the baseline
...
train 01_lightgbm on all           # same model on FD001-FD004
compare cmapss                     # refresh REPORT.md
finalize cmapss                    # 3 seeds, final report, model_registry.json
```
The N-CMAPSS commands are the same with `ncmapss` and a sub-dataset id (`train 01_lightgbm on DS01`).

## 6. Shared protocol (binding for both tracks)

### 6.1 Metrics
Let d = prediction - truth, in RUL units.
- MSE = mean(d^2); RMSE = sqrt(MSE); MAE = mean(|d|); R2 = 1 - SS_res / SS_tot.
- NASA score S = sum of exp(-d/13) - 1 over samples with d < 0 (early prediction) plus exp(d/10) - 1 over samples with d >= 0 (late prediction). Lower is better and late predictions are punished harder. Also report `nasa_score_mean` = S / N so sets of different size can be compared.

| Track | Split | What is scored |
|---|---|---|
| CMAPSS | val | every window of the validation engines vs the clipped training target |
| CMAPSS | test | the last window of each test engine vs the official RUL file, reported twice: `target_type=raw` (official) and `target_type=clipped` (truth capped at the cap) |
| NCMAPSS | val | every validation window vs Y |
| NCMAPSS | test | `level=window` (every test window) and `level=flight_cycle` (mean prediction inside each flight cycle vs that cycle's RUL) |

`results/comparison.csv` columns: `track, dataset, model, seed, split, level, target_type, n, rmse, mae, mse, r2, nasa_score, nasa_score_mean, n_params, train_seconds, device, config_hash, timestamp`. One row per (track, dataset, model, seed, split, level, target_type); re-running a model replaces its rows.

### 6.2 Deep-model training recipe (unless a model spec overrides it)
- AdamW (lr 1e-3, weight decay 1e-4); ReduceLROnPlateau on validation RMSE (factor 0.5, patience 5); gradient clipping 1.0.
- Loss: MSE on the scaled target; metrics always computed in real RUL units.
- At most 150 epochs, early stopping with patience 20 on validation RMSE, restore the best checkpoint.
- Batch size 256 (CMAPSS) or 512 (NCMAPSS). AMP off unless the config enables it.
- Dropout as specified. No data augmentation unless I ask. Same windows and splits for every model.
- Save `history.csv` (epoch, train_loss, val_loss, val_rmse, lr, seconds) and loss/prediction plots.
- Hyperparameters may be tuned on validation data only; log every trial in `outputs/tuning_log.csv`. Never use the test set to choose anything.
- Seeds: develop with 42; final numbers use 42, 43, 44 (mean +- std).

### 6.3 Output contract and the `predict.py` interface
Each model folder ends up with: `config.yaml`, `model.py`, `train.py`, `predict.py` and `outputs/<DATASET>/seed_<n>/` containing the weights, `config_used.yaml`, `metrics.json`, `predictions_val.csv`, `predictions_test.csv`, `history.csv` (deep models) and `figures/`.

`predictions_*.csv` columns: `unit, step, y_true_raw, y_true_clipped (if applicable), y_pred, error (= y_pred - y_true_raw), split`.

Phase B depends on this interface:
```python
def load_model(dataset: str, seed: int | None = None) -> "Predictor": ...

class Predictor:
    def predict_rul(self, history: "pandas.DataFrame") -> dict: ...
```
`history` holds the raw sensor rows of ONE unit in the raw column layout of the dataset files, ordered by time. The predictor loads the saved preprocessor, builds the window itself and returns
`{"rul": float, "rul_unit": "cycles" | "flight_cycles", "n_steps_used": int, "model": str, "dataset": str, "seed": int, "version": str, "warnings": [str]}` where `version` is a hash of config + weights. Model-specific extra keys: 01 `top_contributors`; 03 `attention`; 06 `hi`, `sensor_drift`, `onset_step`; 08 `members`. Short histories are padded and flagged in `warnings`; missing columns raise a clear error. `predict.py` must be importable by file path (importlib) and independent of the working directory.

### 6.4 Results files (per track, written by code, never edited by hand)
`results/data_audit.md`, `results/splits.json`, `results/comparison.csv`, `results/REPORT.md`, `results/figures/`, `results/artifacts/<DATASET>/` (preprocessor, split ids, feature config).

### 6.5 Model registry
`<track>/model_registry.json`, written by `finalize`: for every dataset and model the `predict_module` path, `artifact_dir`, seed, validation RMSE and test metrics, plus `best_by_val_rmse`, `best_by_nasa_score` and `health_indicator_model` (06_autoencoder). Best models are chosen on VALIDATION data, never on test. Phase B reads this file; do not change its shape without updating the Phase B README.

### 6.6 Reporting after each model
a) Append/replace rows in `comparison.csv`, regenerate `REPORT.md`.
b) One table: val and test RMSE/MAE/MSE/NASA/R2, delta vs baseline (%), delta vs best so far (%).
c) Honest verdict: better or worse than the baseline and by how much; whether the gap could be seed noise (with a single seed, say that differences may be within noise); one likely reason; one concrete next improvement.
d) Files created or changed, exact commands run.
e) Stop and wait.

## 7. Acceptance checklist (Phase A is done when all are true)
- [ ] Both datasets audited; `results/data_audit.md` exists in each track and lists every deviation from the README.
- [ ] `common/` built in both tracks; `pytest` passes (parsing, windowing, no-overlap split, scaler fitted on train only, metrics incl. NASA score).
- [ ] Models 01-07 trained on every subset (FD001-FD004) and every N-CMAPSS sub-dataset present, 3 seeds each; model 08 built on top.
- [ ] Every model folder has `config.yaml`, `model.py`, `train.py`, `predict.py` and complete `outputs/`.
- [ ] `results/comparison.csv` and `results/REPORT.md` are final, with mean +- std, honest verdicts and the best model per dataset chosen on validation data.
- [ ] `model_registry.json` exists in both tracks and every predictor loads from it and runs on raw sensor rows.
- [ ] `STATUS.md` updated.

## 8. What comes next
**Phase B - LLM integration** loads `model_registry.json`, serves the predictors behind a FastAPI service, and lets a local Qwen model call them as tools: sensor data in, the LLM routes it, the model predicts, the LLM explains using only the model's own numbers. Nothing in Phase B needs retraining; it only needs the contract in section 6.3 to hold.

### Roadmap
- **Phase A - RUL model training** (`Phase_A_RUL_Training/`): Train and compare eight RUL models on C-MAPSS and N-CMAPSS, one at a time, starting from a LightGBM baseline.  **<- you are here**
- **Phase B - LLM integration** (`Phase_B_LLM_Integration/`): Local Qwen LLM plus the RUL models as tools: data in, the LLM routes it, the model predicts, the LLM explains using only the model's numbers.
- **Phase C - Knowledge base and RAG** (`Phase_C_Knowledge_RAG/`): Real documents, hybrid retrieval and cited cause-chain cards: the evidence chamber.
- **Phase D - Hypothesis engine** (`Phase_D_Hypothesis_Engine/`): The separate brain: competing hypotheses, expected evidence, matching, scoring, follow-up questions and prevention planning.
- **Phase E - Vision** (`Phase_E_Vision/`): Qwen vision-language perception: photos become structured, calibrated evidence.
- **Phase F - Frontend and voice** (`Phase_F_Frontend_Voice/`): UI imported from the Figma design, plus voice in and out. Skeleton only until Phases A-E are accepted.
- **Phase G - Final integration** (`Phase_G_Final_Integration/`): Gateway, model manager, end-to-end tests, full evaluation, packaging and demo.
