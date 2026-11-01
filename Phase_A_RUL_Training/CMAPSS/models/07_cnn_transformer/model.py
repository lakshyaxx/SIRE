"""Hybrid temporal convolution and transformer RUL regressor for CMAPSS."""

from __future__ import annotations

import math
from typing import Any

import torch
from torch import nn


class SinusoidalPositionalEncoding(nn.Module):
    """Add fixed sinusoidal position signals to convolutional features."""

    def __init__(self, d_model: int, max_len: int = 128) -> None:
        """Precompute the positional signals up to ``max_len``."""
        super().__init__()
        if d_model <= 0 or d_model % 2 or max_len <= 0:
            raise ValueError("d_model must be positive and even; max_len must be positive")
        positions = torch.arange(max_len, dtype=torch.float32).unsqueeze(1)
        frequencies = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float32)
            * (-math.log(10000.0) / d_model)
        )
        encoding = torch.zeros(max_len, d_model, dtype=torch.float32)
        encoding[:, 0::2] = torch.sin(positions * frequencies)
        encoding[:, 1::2] = torch.cos(positions * frequencies)
        self.register_buffer("encoding", encoding.unsqueeze(0), persistent=True)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        """Add positional signals to a ``(batch, time, channel)`` tensor."""
        if inputs.shape[1] > self.encoding.shape[1]:
            raise ValueError("sequence length exceeds positional encoding max_len")
        return inputs + self.encoding[:, : inputs.shape[1]]


class CNNTransformerRegressor(nn.Module):
    """Apply two local Conv1d blocks, attention, pooling, and an RUL head."""

    def __init__(
        self,
        input_size: int,
        conv_channels: int = 64,
        conv_kernel_size: int = 5,
        d_model: int = 64,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 128,
        transformer_dropout: float = 0.1,
        positional_max_len: int = 128,
        head_hidden_size: int = 64,
        head_dropout: float = 0.2,
    ) -> None:
        """Build the specified CNN front end and Transformer encoder stack."""
        super().__init__()
        if min(input_size, conv_channels, conv_kernel_size, d_model, nhead,
               num_layers, dim_feedforward, head_hidden_size) <= 0:
            raise ValueError("model dimensions and kernel size must be positive")
        if d_model % nhead != 0:
            raise ValueError("d_model must be divisible by nhead")
        if conv_kernel_size % 2 == 0:
            raise ValueError("conv_kernel_size must be odd to preserve sequence length")
        padding = conv_kernel_size // 2
        self.convolutions = nn.Sequential(
            nn.Conv1d(input_size, conv_channels, conv_kernel_size, padding=padding),
            nn.BatchNorm1d(conv_channels),
            nn.ReLU(),
            nn.Conv1d(conv_channels, conv_channels, conv_kernel_size, padding=padding),
            nn.BatchNorm1d(conv_channels),
            nn.ReLU(),
        )
        self.projection = (
            nn.Identity() if conv_channels == d_model else nn.Linear(conv_channels, d_model)
        )
        self.position = SinusoidalPositionalEncoding(d_model, positional_max_len)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=transformer_dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(
            layer, num_layers=num_layers, enable_nested_tensor=False
        )
        self.regression_head = nn.Sequential(
            nn.Linear(d_model * 2, head_hidden_size),
            nn.ReLU(),
            nn.Dropout(head_dropout),
            nn.Linear(head_hidden_size, 1),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        """Return one scaled RUL estimate for every input window."""
        if inputs.ndim != 3 or inputs.shape[1] == 0:
            raise ValueError("inputs must have shape (batch, non-empty time, channels)")
        features = self.convolutions(inputs.transpose(1, 2)).transpose(1, 2)
        encoded = self.encoder(self.position(self.projection(features)))
        pooled = torch.cat((encoded.mean(dim=1), encoded[:, -1]), dim=1)
        return self.regression_head(pooled)


def build_model(input_size: int, config: dict[str, Any]) -> CNNTransformerRegressor:
    """Construct the hybrid network from YAML-backed hyperparameters."""
    return CNNTransformerRegressor(
        input_size=input_size,
        conv_channels=int(config["conv_channels"]),
        conv_kernel_size=int(config["conv_kernel_size"]),
        d_model=int(config["d_model"]),
        nhead=int(config["nhead"]),
        num_layers=int(config["num_layers"]),
        dim_feedforward=int(config["dim_feedforward"]),
        transformer_dropout=float(config["transformer_dropout"]),
        positional_max_len=int(config["positional_max_len"]),
        head_hidden_size=int(config["head_hidden_size"]),
        head_dropout=float(config["head_dropout"]),
    )
