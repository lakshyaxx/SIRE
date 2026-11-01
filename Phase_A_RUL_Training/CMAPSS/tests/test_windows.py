"""Causal window shape, padding, and target alignment tests."""

import numpy as np
import pandas as pd

from common.windows import WindowDataset, make_test_last_windows, make_windows


def _frame(values: list[float]) -> pd.DataFrame:
    """Build a compact single-engine frame with one channel and labels."""
    return pd.DataFrame(
        {
            "unit": 1,
            "cycle": np.arange(1, len(values) + 1),
            "s1": values,
            "rul_raw": np.arange(len(values) - 1, -1, -1),
            "rul_clipped": np.arange(len(values) - 1, -1, -1),
        }
    )


def test_windows_shape_padding_and_label_endpoint() -> None:
    """Repeat the first row on the left and label each window at its endpoint."""
    windows = make_windows(_frame([10, 20, 30, 40]), ["s1"], window_length=3)
    assert windows.x.shape == (4, 3, 1)
    np.testing.assert_array_equal(windows.x[0, :, 0], [10, 10, 10])
    np.testing.assert_array_equal(windows.x[1, :, 0], [10, 10, 20])
    np.testing.assert_array_equal(windows.x[3, :, 0], [20, 30, 40])
    np.testing.assert_array_equal(windows.y, [3, 2, 1, 0])
    np.testing.assert_array_equal(windows.y_raw, [3, 2, 1, 0])
    assert windows.padded_engines == 0
    x, y = WindowDataset(windows)[0]
    assert tuple(x.shape) == (3, 1)
    assert float(y) == 3


def test_no_future_leakage_and_test_last_padding_count() -> None:
    """Future rows cannot affect earlier windows; short test engines are counted."""
    original = _frame([1, 2, 3, 4, 5])
    changed = original.copy()
    changed.loc[changed["cycle"].eq(5), "s1"] = 9999
    first = make_windows(original, ["s1"], window_length=3)
    second = make_windows(changed, ["s1"], window_length=3)
    np.testing.assert_array_equal(first.x[:4], second.x[:4])
    test = make_test_last_windows(_frame([4, 8]), ["s1"], window_length=4)
    assert test.x.shape == (1, 4, 1)
    np.testing.assert_array_equal(test.x[0, :, 0], [4, 4, 4, 8])
    assert test.padded_engines == 1


def test_each_cycle_gets_one_window_and_condition_id_is_endpoint() -> None:
    """Preserve one label and condition id per observed cycle."""
    frame = _frame([1, 2, 3])
    frame["condition_id"] = [2, 1, 0]
    windows = make_windows(frame, ["s1", "op1"], window_length=2) if "op1" in frame else make_windows(
        frame.assign(op1=0.0), ["s1", "op1"], window_length=2
    )
    np.testing.assert_array_equal(windows.condition_ids, [2, 1, 0])
