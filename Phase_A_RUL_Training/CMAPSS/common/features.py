"""Causal engineered features for LightGBM window models."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

FEATURE_SUFFIXES = (
    "last",
    "mean",
    "std",
    "min",
    "max",
    "slope",
    "last_minus_first",
    "last5_mean_minus_mean",
)


def extract_window_features(
    windows: np.ndarray,
    channel_names: Sequence[str] | None = None,
    condition_ids: np.ndarray | None = None,
) -> pd.DataFrame:
    """Compute per-channel summary features from `(N, L, F)` causal windows."""
    values = np.asarray(windows, dtype=np.float64)
    if values.ndim != 3:
        raise ValueError(f"windows must have shape (N, L, F), got {values.shape}")
    if values.shape[1] < 1 or values.shape[2] < 1:
        raise ValueError("windows must contain at least one step and one channel")
    if not np.isfinite(values).all():
        raise ValueError("windows contain NaN or infinite values")
    names = list(channel_names) if channel_names is not None else [f"f{i}" for i in range(values.shape[2])]
    if len(names) != values.shape[2] or len(set(names)) != len(names):
        raise ValueError("channel_names must have one unique name per input channel")

    n_samples, length, _ = values.shape
    x_axis = np.arange(length, dtype=np.float64)
    centered_x = x_axis - x_axis.mean()
    denominator = float(np.dot(centered_x, centered_x))
    output: dict[str, np.ndarray] = {}
    for index, channel in enumerate(names):
        series = values[:, :, index]
        mean = series.mean(axis=1)
        slope = ((series - mean[:, None]) @ centered_x) / denominator if denominator else np.zeros(n_samples)
        last5_start = max(0, length - 5)
        features = (
            series[:, -1],
            mean,
            series.std(axis=1, ddof=0),
            series.min(axis=1),
            series.max(axis=1),
            slope,
            series[:, -1] - series[:, 0],
            series[:, last5_start:].mean(axis=1) - mean,
        )
        for suffix, feature in zip(FEATURE_SUFFIXES, features):
            output[f"{channel}_{suffix}"] = feature
    if condition_ids is not None:
        condition_array = np.asarray(condition_ids).reshape(-1)
        if condition_array.size != n_samples:
            raise ValueError("condition_ids length must equal the number of windows")
        output["condition_id"] = condition_array.astype(np.float64)
    return pd.DataFrame(output)


def features_from_window_set(
    windows: np.ndarray,
    feature_columns: Sequence[str],
    condition_ids: np.ndarray | None = None,
) -> pd.DataFrame:
    """Extract features using the preprocessor's ordered model channel names."""
    return extract_window_features(windows, channel_names=feature_columns, condition_ids=condition_ids)
