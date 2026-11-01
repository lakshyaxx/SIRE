"""Raw-history predictor contract tests."""

import numpy as np
import pandas as pd
import pytest

from common.config import RAW_COLUMNS, SENSOR_COLUMNS
from common.predictor_base import PredictorBase
from common.preprocess import CMapssPreprocessor


class _ConstantPredictor(PredictorBase):
    """Test predictor that returns a fixed RUL and a diagnostic field."""

    def predict_window(self, window: np.ndarray) -> tuple[float, dict[str, object]]:
        return 12.5, {"test_extra": float(window[0, -1, 0])}


def _raw_frame(unit: int, offset: float, cycles: int) -> pd.DataFrame:
    """Build a raw-layout synthetic engine history."""
    rows = []
    for cycle in range(1, cycles + 1):
        row = {"unit": unit, "cycle": cycle, "op1": 0.0, "op2": 0.0, "op3": 0.0}
        row.update({sensor: offset + cycle if sensor == "s2" else float(index) for index, sensor in enumerate(SENSOR_COLUMNS)})
        rows.append(row)
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


def test_predictor_builds_padded_window_and_contract(tmp_path) -> None:
    """Preprocess raw rows, left pad a short engine, and return contract fields."""
    train = _raw_frame(1, 0.0, 3)
    preprocessor = CMapssPreprocessor("FD001").fit(train, [1])
    predictor = _ConstantPredictor(preprocessor, "demo", "FD001", 42, "abc", window_length=5)
    result = predictor.predict_rul(train.drop(columns="unit"))
    assert result["rul"] == 12.5
    assert result["rul_unit"] == "cycles"
    assert result["n_steps_used"] == 3
    assert result["warnings"]
    assert result["test_extra"] == pytest.approx(np.sqrt(1.5), rel=1e-6)
