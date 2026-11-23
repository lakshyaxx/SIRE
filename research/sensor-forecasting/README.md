# pdm-agent
Predictive maintenance on C-MAPSS (turbofan engines): RUL prediction, health index and uncertainty, with an agentic AI layer to follow.
N-CMAPSS support is stubbed for a later phase.
Start here: PROJECT_MAP.md, then docs/codex_prompts/00_README.md.

Setup:
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt && pip install -e .
Put the C-MAPSS files (train_FD00X.txt, test_FD00X.txt, RUL_FD00X.txt) in data/raw/cmapss/.

## Classical sensor forecasting

These experiments use engine 1, sensor 2 from FD001 by default. Their data
selection and output root are in `configs/forecasting/sensor_experiment.yaml`.
From the repository root, run an experiment with Python after installing the
requirements and the editable package.

| Purpose | Commands |
| --- | --- |
| AR and MA | `python -m scripts.training.ar_model`, `python -m scripts.training.ma_model` |
| Stationarity, seasonality and residuals | `python -m scripts.analysis.stationarity_analysis`, `python -m scripts.analysis.check_seasonality`, `python -m scripts.analysis.residual_analysis` |
| ARIMA, Holt-Winters, SARIMA and overall comparison | `python -m scripts.evaluation.compare_arima`, `python -m scripts.evaluation.compare_holt_winters`, `python -m scripts.evaluation.test_sarima`, `python -m scripts.evaluation.final_comparison` |
| Forecast plots | `python -m scripts.visualization.plot_forecast`, `python -m scripts.visualization.plot_holt_winters` |

The launchers in `diffmodels/` run the same experiments from the repository root.
For example, run `python -m diffmodels.ar_model`.

Existing figures and CSVs live in `results/figures/` and `results/metrics/`.
Each invocation that saves output prints its new directory under
`results/runs/`. Existing results are preserved across runs.

## Fixed-origin sensor benchmark

Install the base environment with `python -m pip install -r requirements.txt`
and `python -m pip install -e .`. Install `python -m pip install -e ".[tft]"`
for TFT. The benchmark consumes the raw C-MAPSS training trajectories and
supports FD001 through FD004. It does not use RUL labels or the processed RUL
windows.

| Model | Targets | Forecast-time inputs |
| --- | --- | --- |
| AR, MA, ARIMA, ARMA | One | Target history |
| SARIMA | One | Target history and a candidate seasonal period |
| ARIMAX, SARIMAX | One | Target history and deterministic future regressors |
| VAR | Multiple | Joint history, information-criterion lag selection |
| VARMA | Multiple | Joint history, AR and MA orders |
| VARIMA | Multiple | Joint history, training-only differencing and original-scale reconstruction |
| VARMAX | Multiple | Joint history and deterministic future regressors |
| SES, Holt Linear | One | Target history |
| Holt-Winters | One | Target history and a candidate period when seasonal smoothing is enabled |
| TFT | One or multiple | Target and other sensor history, static initial settings, future cycle IDs |
| LightGBM | RUL | Engine windows and engineered features in the separate RUL pipeline |

```powershell
python -m pdm.forecasting.benchmark --models arma --targets sensor_2
python -m pdm.forecasting.benchmark --models ar ma arima sarima ses holt arma arimax sarimax var varma varima varmax holt_winters
python -m pdm.forecasting.benchmark --models tft --tft-smoke
python -m pdm.forecasting.benchmark --models tft --full-tft
```

Each command trains and evaluates the selected models. Use `--subset FD002`,
`--unit 1`, `--targets sensor_2 sensor_3`, and `--horizon 39` to select the
benchmark. Univariate models forecast the first listed target. A model can use
overrides from a repository-relative or absolute YAML file with
`--config sarimax=path/to/overrides.yaml`. Base settings and defaults live in
`configs/forecasting/benchmark.yaml` and `configs/models/`.
The models also have individual launchers in `diffmodels/`.

| Model | Command |
| --- | --- |
| ARMA | `python -m diffmodels.sensor2_arma` |
| ARIMAX | `python -m diffmodels.arimax_model` |
| SARIMAX | `python -m diffmodels.sarimax_model` |
| VAR | `python -m diffmodels.var_model` |
| VARMA | `python -m diffmodels.varma_model` |
| VARIMA | `python -m diffmodels.varima_model` |
| VARMAX | `python -m diffmodels.varmax_model` |
| Holt-Winters | `python -m diffmodels.holt_winters_model` |
| TFT | `python -m diffmodels.tft_model` defaults to the CPU smoke profile. Add `--full-tft` for full training. |

Each launcher accepts benchmark options such as `--horizon 20`.

Classical models fit the selected engine's chronological prefix. TFT trains
on other engines, validates on a separate engine group, and uses the benchmark
engine's prefix only at inference. The reported test samples are the same for
matching targets and horizons. The default is one origin on FD001 engine 1,
so the results do not establish performance across engines or datasets.

Exogenous regressors are `cycle` and optionally `log_cycle`, both derived
from the forecast cycle ID. Future sensor readings and operating settings
are unavailable. Seasonal models evaluate a configurable candidate period
and report its training-only differenced ACF against a screening bound.
VARIMA's default first difference is an explicit candidate. Compare the
recorded ADF diagnostics before selecting another integration order.
VARMA-style state-space optimization can fail or be poorly identified,
especially with many targets. A failed fit is recorded without metrics.

The TFT smoke profile uses one CPU epoch, limited batches, and one seed.
Full training uses three seeds, early stopping, and CPU or CUDA where
available. Runtime grows with the number and length of training trajectories.
Full TFT metrics score the mean forecast and retain per-seed scores. To resume,
use the same benchmark, a matching single-seed profile, and a higher
`max_epochs` with `--resume path/to/last.ckpt`. Use locally trusted checkpoint
and pickle files only. TFT uses [PyTorch Forecasting's Temporal Fusion Transformer](https://pytorch-forecasting.readthedocs.io/en/stable/getting-started.html).

Each run writes a manifest, per-target and multivariate macro metrics,
attempt status, forecasts, diagnostics, charts and a winner summary under
`results/runs/sensor-*/`. Model files are at the run root. TFT stores its
training history, preprocessing metadata and checkpoints in `tft-<seed>/`.
CPU smoke scores are marked and excluded from model rankings. RUL commands
and NASA scoring remain documented in `docs/codex_prompts/02_lightgbm_baseline.md`.
