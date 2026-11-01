"""LightGBM parameter mapping and per-channel contribution aggregation tests."""

import sys
from pathlib import Path

import numpy as np

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "01_lightgbm"
sys.path.insert(0, str(MODEL_DIR))

from model import aggregate_channel_contributions, config_hash, regressor_params


def test_default_parameters_match_the_baseline_spec() -> None:
    """Map YAML defaults to the required untuned regression configuration."""
    values = {
        "objective": "regression",
        "metric": "rmse",
        "learning_rate": 0.03,
        "num_leaves": 31,
        "min_data_in_leaf": 20,
        "feature_fraction": 0.7,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "lambda_l2": 1.0,
        "n_estimators": 5000,
    }
    params = regressor_params(values, 42)
    assert {key: params[key] for key in values} == values
    assert params["random_state"] == 42
    assert params["device_type"] == "cpu"
    assert config_hash(values) == config_hash(dict(reversed(list(values.items()))))


def test_contributions_aggregate_to_channels() -> None:
    """Combine sensor-level feature contributions into ranked channel scores."""
    contrib = np.array([[1.0, 2.0, -1.0, 0.0], [-1.0, 2.0, 3.0, 0.5]])
    result = aggregate_channel_contributions(contrib, ["s1_last", "s1_mean", "s2_last"], ["s1", "s2"])
    assert result[0]["channel"] == "s1"
    assert result[0]["mean_abs_contribution"] == 2.0
    assert result[0]["mean_contribution"] == 2.0
    assert result[1]["channel"] == "s2"
    assert result[1]["mean_abs_contribution"] == 2.0
