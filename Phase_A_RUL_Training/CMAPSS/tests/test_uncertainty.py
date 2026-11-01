"""Tests for shared predictive interval calibration and metrics."""

from __future__ import annotations

import numpy as np
import pytest

from common.uncertainty import calibrate_spread_scale, interval_metrics, spread_interval


def test_calibrate_spread_scale_hits_empirical_validation_coverage() -> None:
    truth = np.arange(10, dtype=float)
    prediction = truth + np.arange(10, dtype=float)
    scale = calibrate_spread_scale(truth, prediction, np.ones(10))
    low, high = spread_interval(prediction, np.ones(10), scale)
    assert np.mean((truth >= low) & (truth <= high)) >= 0.8


def test_interval_metrics_reports_coverage_width_and_correlation() -> None:
    result = interval_metrics([1, 2, 3], [0, 1, 2], [2, 3, 4], [1, 1, 1])
    assert result["coverage"] == 1.0
    assert result["mean_width"] == 2.0
    assert result["width_abs_error_correlation"] is None or np.isnan(
        result["width_abs_error_correlation"]
    )


def test_interval_metrics_rejects_crossed_bounds() -> None:
    with pytest.raises(ValueError, match="lower bounds"):
        interval_metrics([1], [2], [1], [1])


def test_calibration_rejects_zero_spread_when_errors_are_nonzero() -> None:
    with pytest.raises(ValueError, match="zero member spread"):
        calibrate_spread_scale([2], [1], [0])
