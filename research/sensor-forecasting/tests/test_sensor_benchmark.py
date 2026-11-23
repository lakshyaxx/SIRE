"""Tests for model fitting, alignment, leakage prevention and artifact isolation."""
import numpy as np
import pandas as pd
import pytest
from statsmodels.tsa.arima.model import ARIMA

from pdm.evaluation.sensor_metrics import score_sensor_forecast
from pdm.forecasting.benchmark_data import known_regressors, read_settings, split_history
from pdm.models import statistical


@pytest.fixture
def signals():
    """Two nonconstant, mildly autocorrelated test signals."""
    rng = np.random.default_rng(20)
    innovations = rng.normal(size=(140, 2))
    values = innovations.copy()
    for i in range(1, len(values)):
        values[i] += 0.4 * values[i - 1] + 0.25 * innovations[i - 1]
    values += 20 + 0.2 * np.sin(2 * np.pi * np.arange(len(values))[:, None] / 10)
    return pd.DataFrame(values, index=pd.RangeIndex(1, 141, name="cycle"),
                        columns=["sensor_2", "sensor_3"])


@pytest.mark.parametrize("model", ["arma", "arimax", "sarimax", "var", "varma", "varima",
                                   "varmax", "holt_winters"])
def test_statistical_forecasts_and_reload(model, signals, tmp_path):
    config = read_settings("models", f"{model}.yaml")
    targets = signals if model in statistical.MULTIVARIATE else signals.iloc[:, :1]
    history, actual = targets.iloc[:-7], targets.iloc[-7:]
    columns = config.get("exog", [])
    fit = statistical.fit_statistical(model, history, config, known_regressors(history.index, columns))
    future = known_regressors(actual.index, columns)
    prediction = fit.predict(actual.index, future)
    assert prediction.shape == actual.shape
    assert len(score_sensor_forecast(actual, prediction)) == actual.shape[1]
    assert fit.diagnostics["history_adf_p"].keys() == set(actual.columns)
    if columns:
        with pytest.raises(ValueError, match="exogenous"):
            fit.predict(actual.index)
    saved = tmp_path / "fit.pkl"
    fit.save(saved)
    pd.testing.assert_frame_equal(statistical.StatisticalFit.load(saved).predict(actual.index, future),
                                  prediction)


def test_arma_matches_arima_with_zero_differencing(signals):
    history = signals.iloc[:-4, :1]
    index = signals.index[-4:]
    actual = statistical.fit_statistical("arma", history, {"order": [1, 0, 1]}).predict(index)
    expected = ARIMA(history.to_numpy()[:, 0], order=(1, 0, 1)).fit().forecast(4)
    np.testing.assert_allclose(actual.iloc[:, 0], expected, atol=1e-7)


@pytest.mark.parametrize("order", [0, 1, 2, 3])
def test_inverse_differencing_restores_polynomial_trajectory(order):
    x = np.arange(10)
    values = np.column_stack([x ** 3 + x, 2 * x ** 2 - 4])
    _, anchors = statistical.difference(values[:7], order)
    full = np.diff(values, n=order, axis=0)
    np.testing.assert_allclose(statistical.integrate(full[-3:], anchors), values[-3:])


def test_invalid_settings_and_nonconvergence(signals, monkeypatch):
    history = signals.iloc[:, :1]
    with pytest.raises(ValueError, match="positive history"):
        statistical.fit_statistical("holt_winters", -history,
                                    {"trend": "mul", "seasonal": "add", "seasonal_periods": 10})
    with pytest.raises(ValueError, match="at least two"):
        statistical.fit_statistical("holt_winters", history, {"seasonal": "add", "seasonal_periods": 100})
    with pytest.raises(ValueError, match="20 consecutive"):
        statistical.fit_statistical("arma", history.iloc[:10], {"order": [1, 0, 1]})
    with pytest.raises(ValueError, match="positive integration"):
        statistical.fit_statistical("varima", signals, {"order": [1, 1], "integration": 0})
    with pytest.raises(ValueError, match="d=0"):
        statistical.fit_statistical("arma", history, {"order": [1, 1, 1]})

    class Failed:
        mle_retvals = {"converged": False}

    monkeypatch.setattr(ARIMA, "fit", lambda *args, **kwargs: Failed())
    with pytest.raises(RuntimeError, match="did not converge"):
        statistical.fit_statistical("arma", history, {"order": [1, 0, 1]})


def test_split_and_exogenous_schema_never_use_future_sensor_readings(signals):
    frame = pd.concat([signals.assign(unit=1), signals.assign(unit=2) * 2])
    history, actual = split_history(frame.reset_index(), 1, ["sensor_2"], 10)
    frame.loc[actual.index, "sensor_2"] = -100
    changed_history, changed_actual = split_history(frame.reset_index(), 1, ["sensor_2"], 10)
    pd.testing.assert_frame_equal(history, changed_history)
    assert not actual.equals(changed_actual)
    pd.testing.assert_frame_equal(known_regressors(actual.index, ["cycle"]),
                                  known_regressors(changed_actual.index, ["cycle"]))
    with pytest.raises(ValueError, match="future-known"):
        known_regressors(actual.index, ["sensor_3"])
    with pytest.raises(ValueError, match="aligned"):
        score_sensor_forecast(actual, actual.shift(1).dropna())
    zero = pd.DataFrame({"sensor_2": [0.0, 0.0]}, index=actual.index[:2])
    assert score_sensor_forecast(zero, zero)[0]["mape"] is None
    assert score_sensor_forecast(zero, zero)[0]["smape"] == 0


def test_benchmark_writes_metrics_and_errors(signals, tmp_path, monkeypatch):
    from pdm.forecasting import benchmark as runner

    frame = signals.assign(unit=1).reset_index()
    monkeypatch.setattr(runner.CMapssLoader, "load_train", lambda self, subset: frame)
    for folder in ("metrics", "figures/forecasts", "figures/diagnostics", "figures/comparisons"):
        (tmp_path / folder).mkdir(parents=True)
    monkeypatch.setattr(runner, "new_run_directory", lambda: tmp_path)
    output = runner.benchmark(["arma", "varma", "tft"], "FD001", 1, ["sensor_2"], 7,
                              {"arma": {"order": [1, 0, 1]}, "varma": {"order": [1, 1]}})
    comparison = pd.read_csv(output / "metrics/model_comparison.csv")
    assert comparison["model"].tolist() == ["arma"]
    attempts = pd.read_csv(output / "metrics/attempts.csv")
    assert attempts["status"].tolist() == ["completed", "failed", "skipped"]
    assert (output / "figures/comparisons/sensor_2_rmse.png").is_file()


@pytest.mark.parametrize("filename, model, options, expected_options", [
    ("sensor2_arma.py", "arma", [], []),
    *[(f"{name}_model.py", name, [], []) for name in
      ("arimax", "sarimax", "var", "varma", "varima", "varmax", "holt_winters")],
    ("tft_model.py", "tft", [], ["--tft-smoke"]),
    ("tft_model.py", "tft", ["--tft-smoke"], ["--tft-smoke"]),
    ("tft_model.py", "tft", ["--full-tft"], ["--full-tft"]),
])
def test_diffmodels_launcher_forwards_options(monkeypatch, filename, model, options, expected_options):
    import runpy
    import sys

    from pdm.common.paths import ROOT
    from pdm.forecasting import benchmark as runner

    path = ROOT / "diffmodels" / filename
    monkeypatch.setattr(sys, "argv", [str(path), *options, "--horizon", "7"])
    calls = []
    monkeypatch.setattr(runner, "main", lambda args: calls.append(args) or 0)
    with pytest.raises(SystemExit) as exit_status:
        runpy.run_module(f"diffmodels.{path.stem}", run_name="__main__")
    assert exit_status.value.code == 0
    assert calls == [["--models", model, *expected_options, "--horizon", "7"]]
