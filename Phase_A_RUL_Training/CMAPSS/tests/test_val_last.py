"""Tests for deterministic test-like validation sampling."""

from __future__ import annotations

import pandas as pd
import pytest

from common.metrics import compute_metrics
from common.val_last import select_val_last, val_last_metrics


def _predictions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"unit": unit, "step": step, "y_true_raw": 10 - step, "y_true_clipped": 10 - step,
             "y_pred": 9 - step, "error": -1, "split": "val"}
            for unit in (1, 2)
            for step in range(1, 8)
        ]
    )


def test_selection_includes_last_and_is_fixed_seed_deterministic() -> None:
    first = select_val_last(_predictions(), random_points=3, seed=42)
    second = select_val_last(_predictions(), random_points=3, seed=42)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 8
    assert first.groupby("unit")["selection_type"].apply(lambda values: (values == "last").sum()).eq(1).all()
    assert first.groupby("unit")["step"].max().eq(7).all()


def test_selection_handles_short_engines_and_rejects_duplicates() -> None:
    short = _predictions().query("unit == 1 and step <= 2")
    assert len(select_val_last(short, random_points=5)) == 2
    duplicate = pd.concat([short, short.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="unique"):
        select_val_last(duplicate)


def test_val_last_metrics_scores_raw_and_clipped_truth() -> None:
    selected = select_val_last(_predictions(), random_points=2)
    scores = val_last_metrics(selected, compute_metrics)
    assert set(scores) == {"raw", "clipped"}
    assert scores["raw"]["n"] == len(selected)
    assert scores["raw"]["rmse"] == scores["clipped"]["rmse"]
