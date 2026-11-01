"""Transformer encoder regressor for C-MAPSS remaining useful life."""

from __future__ import annotations

import math

import torch
from torch import nn


class SinusoidalPositionalEncoding(nn.Module):
    """Add fixed sinusoidal position signals to projected sensor features."""

    def __init__(self, d_model: int, max_len: int = 128) -> None:
        """Precompute positional signals up to ``max_len`` steps."""
        super().__init__()
        if d_model <= 0 or d_model % 2 != 0 or max_len <= 0:
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
        """Add the matching prefix of the positional signal to inputs."""
        if inputs.shape[1] > self.encoding.shape[1]:
            raise ValueError(
                f"sequence length {inputs.shape[1]} exceeds max_len "
                f"{self.encoding.shape[1]}"
            )
        return inputs + self.encoding[:, : inputs.shape[1], :]


class TransformerRegressor(nn.Module):
    """Regress scaled RUL from a fixed window using global self-attention."""

    def __init__(
        self,
        input_size: int,
        d_model: int = 64,
        nhead: int = 4,
        num_layers: int = 3,
        dim_feedforward: int = 128,
        dropout: float = 0.1,
        positional_max_len: int = 128,
        head_hidden_size: int = 64,
        head_dropout: float = 0.2,
    ) -> None:
        """Create the input projection, encoder, pooling, and regression head."""
        super().__init__()
        if min(input_size, d_model, nhead, num_layers, dim_feedforward, head_hidden_size) <= 0:
            raise ValueError("model dimensions must be positive")
        if d_model % nhead != 0:
            raise ValueError("d_model must be divisible by nhead")
        if not 0.0 <= dropout < 1.0 or not 0.0 <= head_dropout < 1.0:
            raise ValueError("dropout probabilities must be in [0, 1)")
        self.input_projection = nn.Linear(input_size, d_model)
        self.position = SinusoidalPositionalEncoding(d_model, positional_max_len)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
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
        """Return one scaled RUL estimate for each `(batch, time, channel)` window."""
        if inputs.ndim != 3 or inputs.shape[1] == 0:
            raise ValueError("inputs must have shape (batch, non-empty time, channels)")
        encoded = self.input_projection(inputs)
        encoded = self.encoder(self.position(encoded))
        pooled = torch.cat((encoded.mean(dim=1), encoded[:, -1, :]), dim=1)
        return self.regression_head(pooled)


def build_model(input_size: int, config: dict[str, object]) -> TransformerRegressor:
    """Construct the transformer from YAML-backed model parameters."""
    return TransformerRegressor(
        input_size=input_size,
        d_model=int(config["d_model"]),
        nhead=int(config["nhead"]),
        num_layers=int(config["num_layers"]),
        dim_feedforward=int(config["dim_feedforward"]),
        dropout=float(config["transformer_dropout"]),
        positional_max_len=int(config["positional_max_len"]),
        head_hidden_size=int(config["head_hidden_size"]),
        head_dropout=float(config["head_dropout"]),
    )
