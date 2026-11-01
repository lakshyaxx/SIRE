"""Architecture tests for the hybrid CNN-Transformer CMAPSS regressor."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import torch

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "07_cnn_transformer" / "model.py"


def _load_model_module():
    spec = importlib.util.spec_from_file_location("test_cnn_transformer_model", MODEL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hybrid_model_shapes_and_spec() -> None:
    module = _load_model_module()
    model = module.CNNTransformerRegressor(input_size=15)
    output = model(torch.randn(3, 30, 15))
    assert output.shape == (3, 1)
    assert model.convolutions[0].out_channels == 64
    assert model.convolutions[3].out_channels == 64
    assert len(model.encoder.layers) == 2
    assert model.encoder.layers[0].self_attn.num_heads == 4
    assert model.encoder.layers[0].linear1.out_features == 128


def test_positional_encoding_rejects_long_sequences() -> None:
    module = _load_model_module()
    position = module.SinusoidalPositionalEncoding(64, max_len=8)
    with pytest.raises(ValueError, match="max_len"):
        position(torch.zeros(2, 9, 64))
