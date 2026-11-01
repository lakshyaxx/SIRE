"""LightGBM regressor construction and contribution aggregation."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import lightgbm as lgb
import numpy as np


def regressor_params(config: Mapping[str, Any], seed: int) -> dict[str, Any]:
    """Map the single-source YAML settings to LightGBM's sklearn API."""
    return {
        "objective": config["objective"],
        "metric": config["metric"],
        "learning_rate": float(config["learning_rate"]),
        "num_leaves": int(config["num_leaves"]),
        "min_data_in_leaf": int(config["min_data_in_leaf"]),
        "feature_fraction": float(config["feature_fraction"]),
        "bagging_fraction": float(config["bagging_fraction"]),
        "bagging_freq": int(config["bagging_freq"]),
        "lambda_l2": float(config["lambda_l2"]),
        "n_estimators": int(config["n_estimators"]),
        "verbosity": int(config.get("verbosity", -1)),
        "n_jobs": int(config.get("n_jobs", -1)),
        "random_state": int(seed),
        "bagging_seed": int(seed),
        "feature_fraction_seed": int(seed),
        "data_random_seed": int(seed),
        "deterministic": bool(config.get("deterministic", True)),
        "force_col_wise": bool(config.get("force_col_wise", True)),
        "device_type": str(config.get("device_type", "cpu")),
    }


def build_regressor(config: Mapping[str, Any], seed: int) -> lgb.LGBMRegressor:
    """Create an untuned or validation-tuned LightGBM regression model."""
    return lgb.LGBMRegressor(**regressor_params(config, seed))


def config_hash(config: Mapping[str, Any]) -> str:
    """Return a stable SHA-256 digest for the run configuration."""
    normalized = json.dumps(dict(config), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _channel_for_feature(feature: str, channels: Sequence[str]) -> str:
    """Map an engineered feature name back to its source channel."""
    if feature == "condition_id":
        return "condition_id"
    for channel in sorted(channels, key=len, reverse=True):
        if feature.startswith(f"{channel}_"):
            return channel
    return feature


def aggregate_channel_contributions(
    contributions: np.ndarray,
    feature_names: Sequence[str],
    channels: Sequence[str],
) -> list[dict[str, float | str]]:
    """Aggregate SHAP-style feature contributions by source channel."""
    values = np.asarray(contributions, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(feature_names) + 1:
        raise ValueError("contributions must contain one column per feature plus the bias column")
    channel_indices: dict[str, list[int]] = defaultdict(list)
    for index, name in enumerate(feature_names):
        channel_indices[_channel_for_feature(name, channels)].append(index)
    output: list[dict[str, float | str]] = []
    for channel, indices in channel_indices.items():
        combined = values[:, indices].sum(axis=1)
        output.append(
            {
                "channel": channel,
                "mean_abs_contribution": float(np.mean(np.abs(combined))),
                "mean_contribution": float(np.mean(combined)),
            }
        )
    return sorted(output, key=lambda item: float(item["mean_abs_contribution"]), reverse=True)


def count_leaf_values(booster: lgb.Booster, num_iteration: int = 0) -> int:
    """Count trained leaf outputs as the model's comparable parameter count."""
    model = booster.dump_model(num_iteration=num_iteration)

    def count_node(node: Mapping[str, Any]) -> int:
        if "leaf_value" in node:
            return 1
        return count_node(node["left_child"]) + count_node(node["right_child"])

    return sum(count_node(tree["tree_structure"]) for tree in model["tree_info"])
