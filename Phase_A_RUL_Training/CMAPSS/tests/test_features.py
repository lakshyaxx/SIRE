"""Feature extraction tests for the LightGBM input contract."""

import numpy as np
import pytest

from common.features import extract_window_features


def test_window_features_match_hand_calculation_and_condition_id() -> None:
    """Compute channel summaries and slope using only the supplied window."""
    values = np.array([[[1.0], [2.0], [3.0], [4.0], [5.0]]])
    features = extract_window_features(values, ["s2"], np.array([4]))
    row = features.iloc[0]
    assert row["s2_last"] == pytest.approx(5.0)
    assert row["s2_mean"] == pytest.approx(3.0)
    assert row["s2_std"] == pytest.approx(np.sqrt(2.0))
    assert row["s2_min"] == pytest.approx(1.0)
    assert row["s2_max"] == pytest.approx(5.0)
    assert row["s2_slope"] == pytest.approx(1.0)
    assert row["s2_last_minus_first"] == pytest.approx(4.0)
    assert row["s2_last5_mean_minus_mean"] == pytest.approx(0.0)
    assert row["condition_id"] == 4


def test_invalid_feature_tensor_is_rejected() -> None:
    """Reject shape and non-finite errors before building model inputs."""
    with pytest.raises(ValueError, match="shape"):
        extract_window_features(np.ones((3, 2)), ["s1"])
    with pytest.raises(ValueError, match="NaN"):
        extract_window_features(np.array([[[np.nan]]]), ["s1"])
