"""Tests for causal health-index degradation forecasts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

MODULE_PATH = (
    (Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "cmapss")
    / "artifacts"
    / "09_ts_degradation"
    / "code"
    / "model.py"
)
SPEC = importlib.util.spec_from_file_location("sire_ts_degradation_model", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODEL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODEL
SPEC.loader.exec_module(MODEL)


def test_ema_is_causal_and_smooths() -> None:
    """Future samples cannot change earlier exponentially smoothed values."""
    values = np.array([0.0, 1.0, 2.0, 3.0, 50.0])
    full = MODEL.ema(values, 3)
    prefix = MODEL.ema(values[:4], 3)
    assert np.allclose(full[:4], prefix)
    assert full[-1] < values[-1]


def test_fit_health_index_and_forecast_contract() -> None:
    """Fit a healthy-only PCA index and return a bounded point/interval."""
    rng = np.random.default_rng(13)
    age = np.tile(np.arange(1, 151), 3)
    healthy = np.clip(180 - age, 0, 125)
    sensors = np.column_stack(
        [
            rng.normal(0, 0.05, len(age)),
            age / age.max() + rng.normal(0, 0.02, len(age)),
            rng.normal(size=len(age)),
        ]
    )
    index = MODEL.fit_health_index(sensors, age, healthy)
    values = MODEL.ema(index.transform(sensors), 5)
    point, interval = MODEL.forecast_rul(
        values[-80:],
        float(np.quantile(values[-60:], 0.8)),
        40,
        "linear",
        bootstrap_samples=20,
    )
    assert np.isfinite(point)
    assert 0 <= interval[0] <= interval[1] <= 125


def test_forecast_rejects_unknown_curve() -> None:
    """Unknown degradation curve names fail explicitly."""
    with pytest.raises(ValueError, match="unsupported trend"):
        MODEL.fit_curve(np.arange(5.0), "cubic")
