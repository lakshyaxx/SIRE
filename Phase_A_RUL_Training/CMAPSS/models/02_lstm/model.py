"""LSTM regression network for C-MAPSS remaining useful life."""

from __future__ import annotations

import torch
from torch import nn


class LSTMRegressor(nn.Module):
    """Regress scaled RUL from a fixed-length, time-ordered sensor window."""

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        lstm_dropout: float = 0.3,
        head_hidden_size: int = 32,
        head_dropout: float = 0.2,
    ) -> None:
        """Create the recurrent encoder and two-layer regression head."""
        super().__init__()
        if (
            input_size <= 0
            or hidden_size <= 0
            or num_layers <= 0
            or head_hidden_size <= 0
        ):
            raise ValueError(
                "model dimensions must be positive"
            )
        if not 0.0 <= lstm_dropout < 1.0 or not 0.0 <= head_dropout < 1.0:
            raise ValueError("dropout probabilities must be in [0, 1)")
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=lstm_dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size, head_hidden_size),
            nn.ReLU(),
            nn.Dropout(head_dropout),
            nn.Linear(head_hidden_size, 1),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        """Return one scaled RUL estimate per `(batch, time, channel)` window."""
        if inputs.ndim != 3:
            raise ValueError("inputs must have shape (batch, time, channels)")
        sequence, _ = self.lstm(inputs)
        return self.head(sequence[:, -1, :])


def build_model(input_size: int, config: dict[str, object]) -> LSTMRegressor:
    """Build the model from the model-specific configuration mapping."""
    return LSTMRegressor(
        input_size=input_size,
        hidden_size=int(config["hidden_size"]),
        num_layers=int(config["num_layers"]),
        lstm_dropout=float(config["lstm_dropout"]),
        head_hidden_size=int(config["head_hidden_size"]),
        head_dropout=float(config["head_dropout"]),
    )
