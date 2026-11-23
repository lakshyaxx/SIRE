"""Tests for engine-safe sliding windows and train-only preprocessing."""
import numpy as np
import pandas as pd

from pdm.data.preprocessing import CMapssPreprocessor
from pdm.data.windowing import make_windows
from pdm.features.engineering import window_features


def test_windows_are_ordered_padded_and_never_cross_units():
    frame = pd.DataFrame({"unit": [1, 1, 2, 2, 2], "cycle": [1, 2, 1, 2, 3],
                          "x": [1, 2, 10, 20, 30], "rul": [1, 0, 2, 1, 0]})
    x, y, units = make_windows(frame, ["x"], window_size=2)
    assert x.shape == (3, 2, 1)
    assert y.tolist() == [0, 1, 0]
    assert units.tolist() == [1, 2, 2]
    np.testing.assert_array_equal(x[0, :, 0], [1, 2])
    np.testing.assert_array_equal(x[1, :, 0], [10, 20])


def test_earlier_window_features_do_not_change_when_future_cycles_change():
    frame = pd.DataFrame({"unit": [1, 1, 1, 1], "cycle": [1, 2, 3, 4],
                          "x": [1.0, 2.0, 3.0, 4.0], "rul": [3, 2, 1, 0]})
    windows, _, _ = make_windows(frame, ["x"], window_size=2)
    changed = frame.copy()
    changed.loc[changed.cycle > 2, "x"] = [300.0, 400.0]
    changed_windows, _, _ = make_windows(changed, ["x"], window_size=2)
    first = window_features(windows[:1], ["x"])
    changed_first = window_features(changed_windows[:1], ["x"])
    np.testing.assert_array_equal(first.to_numpy(), changed_first.to_numpy())
    assert "rul" not in first.columns


def test_preprocessor_drops_constants_and_fits_only_train():
    columns = [f"setting_{i}" for i in range(1, 4)] + [f"sensor_{i}" for i in range(1, 22)]
    train = pd.DataFrame({c: [0.0, 1.0, 2.0] for c in columns})
    train["sensor_1"] = 3.0
    test = train.iloc[:1].copy()
    test["sensor_2"] = 1000.0
    prep = CMapssPreprocessor().fit(train)
    transformed = prep.transform(test)
    assert "sensor_1" in prep.constant_features
    assert transformed.sensor_2.iloc[0] > 1.0


def test_operating_condition_normalization_uses_fitted_clusters():
    columns = [f"setting_{i}" for i in range(1, 4)] + [f"sensor_{i}" for i in range(1, 22)]
    train = pd.DataFrame({c: [0.0, 0.1, 10.0, 10.1] for c in columns})
    train["setting_1"] = [0.0, 0.1, 10.0, 10.1]
    train["setting_2"] = [0.0, 0.1, 1.0, 1.1]
    train["setting_3"] = [60.0, 60.1, 100.0, 100.1]
    train["sensor_1"] = [1.0, 2.0, 100.0, 102.0]
    prep = CMapssPreprocessor(per_condition=True, n_conditions=2)
    transformed = prep.fit_transform(train)
    assert len(prep.condition_stats) == 2
    assert np.isfinite(transformed[prep.features].to_numpy()).all()
