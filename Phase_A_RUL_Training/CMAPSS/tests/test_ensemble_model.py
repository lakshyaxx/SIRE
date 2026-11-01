"""Tests for validation-only ensemble fitting and inference functions."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "08_ensemble" / "model.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("test_ensemble_model_module", MODEL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_fit_ensemble_constraints_and_predictions() -> None:
    module = _load_module()
    target = np.array([1.0, 2.0, 3.0, 4.0])
    predictions = np.column_stack((target + 0.2, target + 1.0, target - 0.5))
    fitted = module.fit_ensembles(predictions, target)
    assert np.all(fitted.weighted_weights >= 0)
    assert fitted.weighted_weights.sum() == pytest.approx(1.0)
    assert np.all(fitted.ridge_coefficients >= 0)
    assert np.allclose(
        module.apply_weighted(predictions, fitted.weighted_weights),
        fitted.weighted_validation,
    )
    assert np.allclose(
        module.apply_ridge(predictions, fitted.ridge_coefficients, fitted.ridge_intercept),
        fitted.ridge_validation,
    )


def test_ensemble_rejects_misaligned_inputs_and_invalid_weights() -> None:
    module = _load_module()
    with pytest.raises(ValueError, match="aligned"):
        module.fit_ensembles(np.ones((3, 2)), np.ones(2))
    with pytest.raises(ValueError, match="sum to one"):
        module.apply_weighted(np.ones((2, 2)), np.array([0.2, 0.2]))
