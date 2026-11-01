"""Shared calibration and evaluation for predictive intervals."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def calibrate_spread_scale(
    y_true: Sequence[float],
    prediction: Sequence[float],
    spread: Sequence[float],
    target_coverage: float = 0.8,
    z_value: float = 1.28,
) -> float:
    """Fit one non-negative interval scale using validation residual ratios."""
    truth = np.asarray(y_true, dtype=float)
    center = np.asarray(prediction, dtype=float)
    sigma = np.asarray(spread, dtype=float)
    if truth.ndim != 1 or center.shape != truth.shape or sigma.shape != truth.shape:
        raise ValueError("y_true, prediction, and spread must be aligned one-dimensional arrays")
    if not np.isfinite(truth).all() or not np.isfinite(center).all() or not np.isfinite(sigma).all():
        raise ValueError("calibration inputs must be finite")
    if np.any(sigma < 0) or z_value <= 0 or not 0 < target_coverage < 1:
        raise ValueError("spread must be non-negative and calibration settings valid")
    positive = sigma > 0
    if not np.any(positive):
        if np.allclose(truth, center):
            return 0.0
        raise ValueError("cannot calibrate non-zero residuals from zero member spread")
    ratios = np.abs(truth[positive] - center[positive]) / (z_value * sigma[positive])
    return float(np.quantile(ratios, target_coverage, method="higher"))


def spread_interval(
    prediction: Sequence[float], spread: Sequence[float], scale: float, z_value: float = 1.28
) -> tuple[np.ndarray, np.ndarray]:
    """Return symmetric prediction intervals from member spread."""
    center = np.asarray(prediction, dtype=float)
    sigma = np.asarray(spread, dtype=float)
    if center.ndim != 1 or sigma.shape != center.shape:
        raise ValueError("prediction and spread must be aligned one-dimensional arrays")
    if not np.isfinite(center).all() or not np.isfinite(sigma).all():
        raise ValueError("prediction and spread must be finite")
    if scale < 0 or z_value <= 0 or np.any(sigma < 0):
        raise ValueError("scale/z_value must be positive and spread non-negative")
    half_width = z_value * float(scale) * sigma
    return center - half_width, center + half_width


def interval_metrics(
    y_true: Sequence[float],
    lower: Sequence[float],
    upper: Sequence[float],
    prediction: Sequence[float],
) -> dict[str, float]:
    """Compute empirical coverage, mean width, and Pearson width-error correlation."""
    truth = np.asarray(y_true, dtype=float)
    low = np.asarray(lower, dtype=float)
    high = np.asarray(upper, dtype=float)
    center = np.asarray(prediction, dtype=float)
    if truth.ndim != 1 or any(array.shape != truth.shape for array in (low, high, center)):
        raise ValueError("interval metric inputs must be aligned one-dimensional arrays")
    if not all(np.isfinite(array).all() for array in (truth, low, high, center)):
        raise ValueError("interval metric inputs must be finite")
    if np.any(low > high):
        raise ValueError("interval lower bounds must not exceed upper bounds")
    widths = high - low
    errors = np.abs(truth - center)
    correlation = float(np.corrcoef(widths, errors)[0, 1]) if len(truth) > 1 and np.std(widths) > 0 and np.std(errors) > 0 else float("nan")
    return {
        "coverage": float(np.mean((truth >= low) & (truth <= high))),
        "mean_width": float(np.mean(widths)),
        "width_abs_error_correlation": correlation,
    }
