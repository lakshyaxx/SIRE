"""Bidirectional LSTM with temporal attention for C-MAPSS RUL."""

from __future__ import annotations

import torch
from torch import nn


class BiLSTMAttentionRegressor(nn.Module):
    """Regress scaled RUL and optionally return temporal attention weights."""

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        encoder_dropout: float = 0.3,
        attention_size: int = 64,
        head_hidden_size: int = 64,
        head_dropout: float = 0.3,
    ) -> None:
        """Build a bidirectional recurrent encoder, attention pool, and head."""
        super().__init__()
        dimensions = (
            input_size,
            hidden_size,
            num_layers,
            attention_size,
            head_hidden_size,
        )
        if any(size <= 0 for size in dimensions):
            raise ValueError("model dimensions must be positive")
        if not 0.0 <= encoder_dropout < 1.0 or not 0.0 <= head_dropout < 1.0:
            raise ValueError("dropout probabilities must be in [0, 1)")

        encoded_size = hidden_size * 2
        self.encoder = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=encoder_dropout if num_layers > 1 else 0.0,
            batch_first=True,
            bidirectional=True,
        )
        self.attention_projection = nn.Linear(encoded_size, attention_size)
        self.attention_score = nn.Linear(attention_size, 1, bias=False)
        self.regression_head = nn.Sequential(
            nn.Linear(encoded_size * 2, head_hidden_size),
            nn.ReLU(),
            nn.Dropout(head_dropout),
            nn.Linear(head_hidden_size, 1),
        )

    def forward(
        self,
        inputs: torch.Tensor,
        return_attention: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
        """Return scaled RUL, optionally paired with `(batch, time)` attention."""
        if inputs.ndim != 3 or inputs.shape[1] == 0:
            raise ValueError("inputs must have shape (batch, non-empty time, channels)")
        encoded, _ = self.encoder(inputs)
        scores = self.attention_score(torch.tanh(self.attention_projection(encoded)))
        attention = torch.softmax(scores.squeeze(-1), dim=1)
        context = torch.bmm(attention.unsqueeze(1), encoded).squeeze(1)
        last_step = encoded[:, -1, :]
        prediction = self.regression_head(torch.cat((context, last_step), dim=1))
        if return_attention:
            return prediction, attention
        return prediction


def build_model(input_size: int, config: dict[str, object]) -> BiLSTMAttentionRegressor:
    """Construct the model using values from the model configuration."""
    return BiLSTMAttentionRegressor(
        input_size=input_size,
        hidden_size=int(config["hidden_size"]),
        num_layers=int(config["num_layers"]),
        encoder_dropout=float(config["encoder_dropout"]),
        attention_size=int(config["attention_size"]),
        head_hidden_size=int(config["head_hidden_size"]),
        head_dropout=float(config["head_dropout"]),
    )
