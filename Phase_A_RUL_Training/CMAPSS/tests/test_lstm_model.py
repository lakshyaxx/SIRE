"""Shape and configuration checks for the C-MAPSS LSTM model."""

import importlib.util
from pathlib import Path

import pytest
import torch

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "02_lstm"
MODEL_SPEC = importlib.util.spec_from_file_location(
    "sire_cmapss_02_lstm_model_test", MODEL_DIR / "model.py"
)
assert MODEL_SPEC is not None and MODEL_SPEC.loader is not None
MODEL_MODULE = importlib.util.module_from_spec(MODEL_SPEC)
MODEL_SPEC.loader.exec_module(MODEL_MODULE)
LSTMRegressor = MODEL_MODULE.LSTMRegressor


def test_lstm_regressor_outputs_one_rul_per_window() -> None:
    """The specified recurrent network maps (batch, time, sensors) to (batch, 1)."""
    model = LSTMRegressor(input_size=15, hidden_size=64, num_layers=2)
    output = model(torch.zeros(4, 30, 15))

    assert output.shape == (4, 1)
    assert torch.isfinite(output).all()


def test_lstm_regressor_rejects_non_sequence_input() -> None:
    """Malformed tensors fail with an explicit shape error."""
    model = LSTMRegressor(input_size=15)

    with pytest.raises(ValueError, match="batch, time, channels"):
        model(torch.zeros(4, 15))
