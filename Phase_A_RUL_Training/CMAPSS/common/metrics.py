"""Regression and NASA asymmetric scoring metrics in RUL units."""

from __future__ import annotations

import numpy as np


def _arrays(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert inputs to aligned finite one-dimensional arrays."""
    truth = np.asarray(y_true, dtype=np.float64).reshape(-1)
    prediction = np.asarray(y_pred, dtype=np.float64).reshape(-1)
    if truth.shape != prediction.shape:
        raise ValueError(f"y_true and y_pred must have the same shape, got {truth.shape} and {prediction.shape}")
    if truth.size == 0:
        raise ValueError("metrics require at least one observation")
    if not np.isfinite(truth).all() or not np.isfinite(prediction).all():
        raise ValueError("metrics inputs must be finite")
    return truth, prediction


def mse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Return mean squared error."""
    truth, prediction = _arrays(y_true, y_pred)
    return float(np.mean(np.square(prediction - truth)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Return root mean squared error."""
    return float(np.sqrt(mse(y_true, y_pred)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Return mean absolute error."""
    truth, prediction = _arrays(y_true, y_pred)
    return float(np.mean(np.abs(prediction - truth)))


def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Return coefficient of determination; use 0 when truth is constant."""
    truth, prediction = _arrays(y_true, y_pred)
    total = float(np.square(truth - truth.mean()).sum())
    if total == 0.0:
        return 0.0
    return float(1.0 - np.square(prediction - truth).sum() / total)


def nasa_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Return the NASA asymmetric score; late predictions have a 10-cycle scale."""
    truth, prediction = _arrays(y_true, y_pred)
    difference = prediction - truth
    early = difference < 0
    contributions = np.empty_like(difference)
    contributions[early] = np.exp(-difference[early] / 13.0) - 1.0
    contributions[~early] = np.exp(difference[~early] / 10.0) - 1.0
    return float(contributions.sum())


def nasa_score_mean(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Return mean NASA score per observation."""
    truth, prediction = _arrays(y_true, y_pred)
    return nasa_score(truth, prediction) / truth.size


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float | int]:
    """Compute all shared Phase A metrics for a non-empty evaluation set."""
    truth, prediction = _arrays(y_true, y_pred)
    return {
        "n": int(truth.size),
        "mse": mse(truth, prediction),
        "rmse": rmse(truth, prediction),
        "mae": mae(truth, prediction),
        "r2": r2(truth, prediction),
        "nasa_score": nasa_score(truth, prediction),
        "nasa_score_mean": nasa_score_mean(truth, prediction),
    }


def compute_metric_mapping(y_true: np.ndarray, y_pred: np.ndarray) -> Mapping[str, float | int]:
    """Typed alias for consumers that expect a read-only metrics mapping."""
    return compute_metrics(y_true, y_pred)
