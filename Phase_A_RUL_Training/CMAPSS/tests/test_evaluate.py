"""Shared validation and official-test evaluation tests."""

import numpy as np

from common.evaluate import evaluate_predictions


def test_test_metrics_use_raw_and_capped_truth_separately() -> None:
    """Only truth is capped for the clipped test score; predictions stay raw."""
    result = evaluate_predictions(
        y_val_clipped=np.array([10.0, 20.0]),
        y_val_pred=np.array([11.0, 22.0]),
        y_test_raw=np.array([200.0, 50.0]),
        y_test_pred=np.array([150.0, 60.0]),
        rul_cap=125.0,
    )
    assert result["val"]["n"] == 2
    assert result["test_raw"]["mae"] == 30.0
    assert result["test_clipped"]["mae"] == 17.5

