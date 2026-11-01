"""Hand-computed metric validation, including the asymmetric NASA score."""

import numpy as np
import pytest

from common.metrics import compute_metrics, mae, mse, nasa_score, r2, rmse


def test_regression_metrics_match_hand_calculation() -> None:
    """Check common regression scores on a small exact example."""
    truth = np.array([1.0, 3.0, 5.0])
    pred = np.array([2.0, 1.0, 7.0])
    assert mse(truth, pred) == pytest.approx(3.0)
    assert rmse(truth, pred) == pytest.approx(np.sqrt(3.0))
    assert mae(truth, pred) == pytest.approx(5.0 / 3.0)
    assert r2(truth, pred) == pytest.approx(1.0 - 9.0 / 8.0)
    assert compute_metrics(truth, pred)["n"] == 3


def test_nasa_score_uses_asymmetric_early_and_late_penalties() -> None:
    """Verify score terms directly for one early and one late prediction."""
    truth = np.array([10.0, 10.0])
    pred = np.array([0.0, 20.0])
    expected = (np.exp(10.0 / 13.0) - 1.0) + (np.exp(10.0 / 10.0) - 1.0)
    assert nasa_score(truth, pred) == pytest.approx(expected)
    assert nasa_score(truth, np.array([20.0, 20.0])) > nasa_score(truth, np.array([0.0, 0.0]))


def test_metric_shapes_and_empty_inputs_are_rejected() -> None:
    """Reject invalid vectors instead of returning misleading metric values."""
    with pytest.raises(ValueError, match="same shape"):
        mae(np.array([1, 2]), np.array([1]))
    with pytest.raises(ValueError, match="at least one"):
        r2(np.array([]), np.array([]))
