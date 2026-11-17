"""Tests for the autoencoder architecture and health diagnostics."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

MODEL_DIR = (
    (Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "cmapss")
    / "artifacts"
    / "06_autoencoder"
    / "code"
)


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_autoencoder_architectures_reconstruct_windows_without_rul_head() -> None:
    model_module = _module("test_autoencoder_model_module", MODEL_DIR / "model.py")
    values = torch.randn(4, 30, 8)
    for architecture in ("lstm", "conv1d"):
        model = model_module.build_autoencoder(
            8,
            {
                "architecture": architecture,
                "hidden_size": 32,
                "latent_size": 8,
                "num_layers": 1,
            },
        )
        latent, reconstructed = model(values)
        assert latent.shape == (4, 8)
        assert reconstructed.shape == values.shape
    assert not hasattr(model_module, "HealthRULModel")


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


def test_label_free_health_indicator_quality_definition() -> None:
    health = _module("test_autoencoder_health_quality", MODEL_DIR / "health.py")
    frame = pd.DataFrame({"unit": [1] * 4, "step": [1, 2, 3, 4], "hi": [0, 1, 2, 3]})
    result = health.prognostic_quality(frame)
    assert result["spearman_hi_cycle"] == pytest.approx(1.0)
    assert result["mean_unit_monotonicity"] == pytest.approx(1.0)
    assert result["mean_unit_trendability"] == pytest.approx(1.0)
    assert 0.0 <= result["prognosability"] <= 1.0


def test_causal_smoothing_and_condition_threshold_onset() -> None:
    health = _module("test_autoencoder_health_causal", MODEL_DIR / "health.py")
    scores = health.smooth_by_engine(
        np.array([0.0, 1.0, 1.0]), np.array([1, 1, 1]), span=3
    )
    assert scores[0] == pytest.approx(0.0)
    assert scores[1] == pytest.approx(0.5)
    assert (
        health.onset_with_thresholds([1, 2, 3, 4], [0, 2, 2, 0], [1, 1, 1, 1], 2) == 2
    )
