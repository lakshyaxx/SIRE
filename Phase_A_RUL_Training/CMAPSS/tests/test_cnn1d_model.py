"""Architecture checks for the C-MAPSS 1D-CNN model."""

import importlib.util
from pathlib import Path

import pytest
import torch

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "04_cnn1d"
MODEL_SPEC = importlib.util.spec_from_file_location(
    "sire_cmapss_04_cnn1d_model_test", MODEL_DIR / "model.py"
)
assert MODEL_SPEC is not None and MODEL_SPEC.loader is not None
MODEL_MODULE = importlib.util.module_from_spec(MODEL_SPEC)
MODEL_SPEC.loader.exec_module(MODEL_MODULE)
CNN1DRegressor = MODEL_MODULE.CNN1DRegressor


def test_cnn1d_pools_time_and_returns_one_rul_per_window() -> None:
    """Global average/max pooling produces one regression output per sample."""
    model = CNN1DRegressor(input_size=15)
    output = model(torch.zeros(4, 30, 15))

    assert output.shape == (4, 1)
    assert torch.isfinite(output).all()


def test_cnn1d_rejects_empty_sequence() -> None:
    """Malformed zero-length windows raise an explicit input-shape error."""
    model = CNN1DRegressor(input_size=15)

    with pytest.raises(ValueError, match="non-empty time"):
        model(torch.zeros(2, 0, 15))


def test_cnn1d_requires_three_convolution_blocks() -> None:
    """Model configuration must provide the architecture's three blocks."""
    with pytest.raises(ValueError, match="exactly three"):
        CNN1DRegressor(input_size=15, conv_channels=(64, 128))
