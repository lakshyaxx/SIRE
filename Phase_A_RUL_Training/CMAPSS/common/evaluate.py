"""Shared validation and official test evaluation routines."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from .metrics import compute_metrics


def evaluate_predictions(
    y_val_clipped: np.ndarray,
    y_val_pred: np.ndarray,
    y_test_raw: np.ndarray,
    y_test_pred: np.ndarray,
    rul_cap: float = 125.0,
) -> dict[str, dict[str, float | int]]:
    """Score all validation windows and official test predictions raw/clipped."""
    if rul_cap <= 0:
        raise ValueError("rul_cap must be positive")
    raw = np.asarray(y_test_raw, dtype=np.float64).reshape(-1)
    return {
        "val": dict(compute_metrics(y_val_clipped, y_val_pred)),
        "test_raw": dict(compute_metrics(raw, y_test_pred)),
        "test_clipped": dict(compute_metrics(np.minimum(raw, rul_cap), y_test_pred)),
    }


def evaluate_model(
    model: object,
    x_val: np.ndarray,
    y_val: np.ndarray,
    x_test: np.ndarray,
    y_test_raw: np.ndarray,
    rul_cap: float = 125.0,
) -> tuple[dict[str, dict[str, float | int]], np.ndarray, np.ndarray]:
    """Call an estimator on validation/test inputs and return metrics and predictions."""
    if not hasattr(model, "predict"):
        raise TypeError("model must expose predict(X)")
    val_pred = np.asarray(model.predict(x_val), dtype=np.float64).reshape(-1)
    test_pred = np.asarray(model.predict(x_test), dtype=np.float64).reshape(-1)
    metrics: Mapping[str, Mapping[str, float | int]] = evaluate_predictions(
        y_val, val_pred, y_test_raw, test_pred, rul_cap=rul_cap
    )
    return {key: dict(value) for key, value in metrics.items()}, val_pred, test_pred
