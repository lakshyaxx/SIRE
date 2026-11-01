"""Tests for the autoencoder architecture and health diagnostics."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "06_autoencoder"


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_autoencoder_shapes_and_health_rul_head() -> None:
    model_module = _module("test_autoencoder_model_module", MODEL_DIR / "model.py")
    autoencoder = model_module.SequenceAutoencoder(input_size=8)
    model = model_module.HealthRULModel(autoencoder)
    values = torch.randn(4, 30, 8)
    means = torch.zeros(8)
    stds = torch.ones(8)
    prediction, latent, drift, hi = model(values, means, stds, 0.0, 1.0)
    assert prediction.shape == (4, 1)
    assert latent.shape == (4, 16)
    assert drift.shape == (4, 8)
    assert hi.shape == (4, 1)


def test_health_calibration_and_onset() -> None:
    health = _module("test_autoencoder_health_module", MODEL_DIR / "health.py")
    errors = np.array([[1.0, 2.0], [2.0, 4.0], [3.0, 6.0]])
    means, stds, hi_mean, hi_std = health.calibrate_health(errors)
    assert np.allclose(means, [2.0, 4.0])
    assert np.all(stds > 0)
    assert hi_mean == pytest.approx(0.0)
    assert hi_std > 0
    assert health.detect_onset(np.arange(1, 8), [0, 1, 4, 4, 4, 4, 4], 3, 5) == 3
    assert health.detect_onset(np.arange(1, 5), [0, 4, 4, 4], 3, 5) is None


def test_prognostic_quality_definition() -> None:
    health = _module("test_autoencoder_health_quality", MODEL_DIR / "health.py")
    frame = pd.DataFrame(
        {"unit": [1] * 4, "step": [1, 2, 3, 4], "hi": [0, 1, 2, 3], "rul_raw": [3, 2, 1, 0]}
    )
    result = health.prognostic_quality(frame)
    assert result["spearman_hi_rul"] == pytest.approx(-1.0)
    assert result["mean_unit_monotonicity"] == pytest.approx(1.0)
    assert result["mean_unit_trendability"] == pytest.approx(1.0)
