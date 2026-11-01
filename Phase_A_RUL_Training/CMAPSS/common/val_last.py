"""Deterministic test-like validation sampling from per-cycle predictions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd


PREDICTION_COLUMNS = ("unit", "step", "y_true_raw", "y_true_clipped", "y_pred")


def select_val_last(
    predictions: pd.DataFrame,
    random_points: int = 5,
    seed: int = 42,
) -> pd.DataFrame:
    """Select each engine's last prediction and fixed-seed random truncations.

    The selected rows are drawn from already-produced validation predictions,
    so this helper never fits on or reads official test data. Random points are
    sampled without replacement from each engine's non-final endpoints.
    """
    if random_points < 0:
        raise ValueError("random_points must be non-negative")
    missing = set(PREDICTION_COLUMNS) - set(predictions.columns)
    if missing:
        raise ValueError(f"Validation predictions are missing columns: {sorted(missing)}")
    if predictions.empty:
        raise ValueError("Validation predictions cannot be empty")
    frame = predictions.copy()
    if frame[list(PREDICTION_COLUMNS)].isna().any().any():
        raise ValueError("Validation prediction fields cannot contain missing values")
    if frame.duplicated(["unit", "step"]).any():
        raise ValueError("Validation predictions must have unique (unit, step) rows")

    selected: list[pd.DataFrame] = []
    for unit, group in frame.sort_values(["unit", "step"], kind="stable").groupby("unit", sort=True):
        group = group.reset_index(drop=True)
        last_index = len(group) - 1
        random_count = min(random_points, last_index)
        if random_count:
            rng = np.random.default_rng(np.random.SeedSequence([int(seed), int(unit)]))
            random_indices = np.sort(rng.choice(last_index, size=random_count, replace=False))
        else:
            random_indices = np.empty(0, dtype=np.int64)
        chosen = group.iloc[np.append(random_indices, last_index)].copy()
        chosen["selection_type"] = ["random"] * random_count + ["last"]
        selected.append(chosen)
    return pd.concat(selected, ignore_index=True).sort_values(
        ["unit", "step"], kind="stable"
    ).reset_index(drop=True)


def val_last_metrics(
    selected_predictions: pd.DataFrame,
    metrics_function: Callable[[np.ndarray, np.ndarray], dict[str, Any]],
) -> dict[str, dict[str, float | int]]:
    """Score selected validation rows against raw and clipped RUL labels."""
    missing = set(PREDICTION_COLUMNS) - set(selected_predictions.columns)
    if missing:
        raise ValueError(f"Selected validation rows are missing columns: {sorted(missing)}")
    compute = metrics_function
    truth_raw = selected_predictions["y_true_raw"].to_numpy(dtype=float)
    prediction = selected_predictions["y_pred"].to_numpy(dtype=float)
    truth_clipped = selected_predictions["y_true_clipped"].to_numpy(dtype=float)
    return {
        "raw": dict(compute(truth_raw, prediction)),
        "clipped": dict(compute(truth_clipped, prediction)),
    }
