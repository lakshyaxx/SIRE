"""Train-only statistics and condition-aware preprocessing tests."""

import numpy as np
import pandas as pd

from common.config import SENSOR_COLUMNS, SETTING_COLUMNS
from common.preprocess import CMapssPreprocessor


def _synthetic_frame() -> pd.DataFrame:
    """Create two engines whose sensor distributions are deliberately separated."""
    rows = []
    for unit, sensor_values in ((1, [1.0, 3.0]), (2, [1000.0, 2000.0])):
        for cycle, value in enumerate(sensor_values, start=1):
            row = {"unit": unit, "cycle": cycle, "op1": 0.0, "op2": 0.0, "op3": 0.0}
            row.update({sensor: value if sensor == "s2" else 7.0 for sensor in SENSOR_COLUMNS})
            rows.append(row)
    return pd.DataFrame(rows)


def test_scaler_is_fitted_only_on_training_engines() -> None:
    """Validation engine extremes must not alter training means or sensor drops."""
    frame = _synthetic_frame()
    preprocessor = CMapssPreprocessor("FD001").fit(frame, [1])
    assert preprocessor.global_sensor_stats["s2"][0] == 2.0
    assert set(preprocessor.dropped_sensors) == set(SENSOR_COLUMNS) - {"s2"}
    transformed = preprocessor.transform(frame)
    np.testing.assert_allclose(transformed.loc[transformed["unit"].eq(1), "s2"], [-1.0, 1.0])
    assert transformed.loc[transformed["unit"].eq(2), "s2"].mean() > 1000


def test_multi_condition_preprocessor_adds_standardized_settings() -> None:
    """Multi-condition models normalize settings and keep a condition id channel."""
    rows = []
    for unit in range(1, 7):
        for cycle in range(1, 4):
            row = {
                "unit": unit,
                "cycle": cycle,
                "op1": float(unit % 3),
                "op2": float(unit // 3),
                "op3": float(unit % 2),
            }
            row.update({sensor: float(unit + cycle) if sensor == "s3" else float(sensor_index) for sensor_index, sensor in enumerate(SENSOR_COLUMNS)})
            rows.append(row)
    frame = pd.DataFrame(rows)
    frame["s3"] = frame["s3"].astype("int64")
    fitted = CMapssPreprocessor("FD002").fit(frame, [1, 2, 3, 4, 5, 6])
    transformed = fitted.transform(frame)
    assert fitted.n_conditions == 6
    assert all(setting in fitted.feature_columns for setting in SETTING_COLUMNS)
    assert "condition_id" in transformed
    assert transformed["s3"].dtype == np.float64
    np.testing.assert_allclose(transformed[list(SETTING_COLUMNS)].mean(), 0.0, atol=1e-7)
