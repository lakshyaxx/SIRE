"""One-dimensional convolutional regressor for C-MAPSS RUL."""

from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import nn


class CNN1DRegressor(nn.Module):
    """Regress scaled RUL from local sensor patterns in a fixed window."""

    def __init__(
        self,
        input_size: int,
        conv_channels: Sequence[int] = (64, 128, 128),
        conv_kernels: Sequence[int] = (5, 5, 3),
        conv_dropout: float = 0.2,
        head_hidden_size: int = 64,
        head_dropout: float = 0.3,
    ) -> None:
        """Create the three convolution blocks and pooled regression head."""
        super().__init__()
        if input_size <= 0 or head_hidden_size <= 0:
            raise ValueError("input_size and head_hidden_size must be positive")
        if len(conv_channels) != 3 or len(conv_kernels) != 3:
            raise ValueError(
                "exactly three convolution channels and kernels are required"
            )
        if any(value <= 0 for value in (*conv_channels, *conv_kernels)):
            raise ValueError("convolution channels and kernel sizes must be positive")
        if not 0.0 <= conv_dropout < 1.0 or not 0.0 <= head_dropout < 1.0:
            raise ValueError("dropout probabilities must be in [0, 1)")

        layers: list[nn.Module] = []
        in_channels = input_size
        for index, (out_channels, kernel_size) in enumerate(
            zip(conv_channels, conv_kernels, strict=True)
        ):
            layers.extend(
                [
                    nn.Conv1d(
                        in_channels,
                        int(out_channels),
                        kernel_size=int(kernel_size),
                        padding=int(kernel_size) // 2,
                    ),
                    nn.BatchNorm1d(int(out_channels)),
                    nn.ReLU(),
                ]
            )
            if index == 1:
                layers.append(nn.Dropout(conv_dropout))
            in_channels = int(out_channels)
        self.convolutions = nn.Sequential(*layers)
        pooled_size = int(conv_channels[-1]) * 2
        self.regression_head = nn.Sequential(
            nn.Linear(pooled_size, head_hidden_size),
            nn.ReLU(),
            nn.Dropout(head_dropout),
            nn.Linear(head_hidden_size, 1),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        """Return one scaled RUL estimate for each `(batch, time, channel)` window."""
        if inputs.ndim != 3 or inputs.shape[1] == 0:
            raise ValueError("inputs must have shape (batch, non-empty time, channels)")
        channels_first = inputs.transpose(1, 2)
        features = self.convolutions(channels_first)
        pooled = torch.cat((features.mean(dim=2), features.amax(dim=2)), dim=1)
        return self.regression_head(pooled)


def build_model(input_size: int, config: dict[str, object]) -> CNN1DRegressor:
    """Construct the CNN from its YAML-backed hyperparameters."""
    return CNN1DRegressor(
        input_size=input_size,
        conv_channels=tuple(int(value) for value in config["conv_channels"]),
        conv_kernels=tuple(int(value) for value in config["conv_kernels"]),
        conv_dropout=float(config["conv_dropout"]),
        head_hidden_size=int(config["head_hidden_size"]),
        head_dropout=float(config["head_dropout"]),
    )
