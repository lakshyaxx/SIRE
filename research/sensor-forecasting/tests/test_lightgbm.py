"""Tests for Phase 2 feature engineering and RUL metrics."""
import numpy as np
import pytest

from pdm.evaluation.metrics import nasa_score, regression_metrics
from pdm.features.engineering import window_features
from pdm.models.lightgbm_model import LightGBMRULRegressor
from pdm.training.train import _terminal_indices


def test_engineered_window_features_have_consistent_order():
    windows = np.array([[[1, 2], [2, 4], [3, 6]]], dtype=np.float32)
    result = window_features(windows, ["a", "b"])
    assert result.columns.tolist() == ["a_last", "b_last", "a_mean", "b_mean", "a_std", "b_std", "a_trend", "b_trend"]
    assert result.loc[0, "a_last"] == 3
    assert result.loc[0, "a_trend"] == pytest.approx(1)


def test_nasa_score_penalizes_late_predictions_more():
    truth = np.array([100.0])
    assert nasa_score(truth, [110]) > nasa_score(truth, [90])
    assert regression_metrics(truth, [100]) == {"mae": 0.0, "rmse": 0.0, "nasa_score": 0.0}


def test_terminal_indices_select_one_window_per_engine():
    units = np.array([1, 1, 1, 2, 2, 3])
    indices = _terminal_indices(units)
    assert indices.tolist() == [2, 4, 5]


def test_raw_and_clipped_rul_metrics_are_distinct_when_raw_exceeds_clip():
    raw = np.array([140.0])
    prediction = np.array([125.0])
    clipped = np.minimum(raw, 125)
    assert regression_metrics(raw, prediction)["mae"] == 15
    assert regression_metrics(clipped, prediction)["mae"] == 0


def test_lightgbm_model_save_and_reload(tmp_path):
    import pandas as pd

    x = pd.DataFrame({"x": np.linspace(0, 1, 30)})
    y = np.linspace(0, 100, 30)
    model = LightGBMRULRegressor(n_estimators=10, random_state=3).fit(x, y)
    expected = model.predict(x)
    path = tmp_path / "baseline.txt"
    model.save(path)
    actual = LightGBMRULRegressor.load(path).predict(x)
    np.testing.assert_allclose(actual, expected)
