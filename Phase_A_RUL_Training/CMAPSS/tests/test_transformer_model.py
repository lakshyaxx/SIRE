"""Architecture checks for the C-MAPSS transformer model."""

import importlib.util
from pathlib import Path

import pytest
import torch

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "05_transformer"
MODEL_SPEC = importlib.util.spec_from_file_location(
    "sire_cmapss_05_transformer_model_test", MODEL_DIR / "model.py"
)
assert MODEL_SPEC is not None and MODEL_SPEC.loader is not None
MODEL_MODULE = importlib.util.module_from_spec(MODEL_SPEC)
MODEL_SPEC.loader.exec_module(MODEL_MODULE)
SinusoidalPositionalEncoding = MODEL_MODULE.SinusoidalPositionalEncoding
TransformerRegressor = MODEL_MODULE.TransformerRegressor


def test_transformer_returns_one_rul_per_window() -> None:
    """The configured encoder reduces each window to one scalar prediction."""
    model = TransformerRegressor(input_size=15, positional_max_len=30)
    output = model(torch.zeros(3, 30, 15))

    assert output.shape == (3, 1)
    assert torch.isfinite(output).all()


def test_positional_encoding_rejects_too_long_sequence() -> None:
    """Windows cannot exceed the configured positional-encoding capacity."""
    encoding = SinusoidalPositionalEncoding(d_model=64, max_len=10)

    with pytest.raises(ValueError, match="exceeds max_len"):
        encoding(torch.zeros(2, 11, 64))


def test_transformer_rejects_invalid_head_dimension() -> None:
    """Attention head count must evenly divide the model dimension."""
    with pytest.raises(ValueError, match="divisible"):
        TransformerRegressor(input_size=15, d_model=64, nhead=3)
