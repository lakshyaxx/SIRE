"""Architecture and attention normalization checks for model 03."""

import importlib.util
from pathlib import Path

import pytest
import torch

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "03_bilstm_attention"
MODEL_SPEC = importlib.util.spec_from_file_location(
    "sire_cmapss_03_bilstm_attention_model_test", MODEL_DIR / "model.py"
)
assert MODEL_SPEC is not None and MODEL_SPEC.loader is not None
MODEL_MODULE = importlib.util.module_from_spec(MODEL_SPEC)
MODEL_SPEC.loader.exec_module(MODEL_MODULE)
BiLSTMAttentionRegressor = MODEL_MODULE.BiLSTMAttentionRegressor


def test_bilstm_returns_prediction_and_normalized_attention() -> None:
    """The bidirectional model emits one estimate and unit-sum temporal weights."""
    model = BiLSTMAttentionRegressor(input_size=15)
    prediction, attention = model(torch.zeros(3, 30, 15), return_attention=True)

    assert prediction.shape == (3, 1)
    assert attention.shape == (3, 30)
    assert torch.allclose(attention.sum(dim=1), torch.ones(3))
    assert torch.isfinite(prediction).all()


def test_bilstm_default_forward_returns_tensor() -> None:
    """Training can call the network as a plain regressor."""
    model = BiLSTMAttentionRegressor(input_size=15)

    assert model(torch.zeros(2, 30, 15)).shape == (2, 1)


def test_bilstm_rejects_empty_sequence() -> None:
    """Zero-length windows fail with an explicit input-shape error."""
    model = BiLSTMAttentionRegressor(input_size=15)

    with pytest.raises(ValueError, match="non-empty time"):
        model(torch.zeros(2, 0, 15))
