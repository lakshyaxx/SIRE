"""Sequence autoencoder and health-informed RUL regression head."""

from __future__ import annotations

from typing import Any

import torch
from torch import nn


class SequenceAutoencoder(nn.Module):
    """Encode a sensor window to a compact vector and reconstruct its sequence."""

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        latent_size: int = 16,
        decoder_hidden_size: int = 64,
        dropout: float = 0.1,
    ) -> None:
        """Build LSTM encoder, latent projection, and recurrent decoder."""
        super().__init__()
        if min(input_size, hidden_size, num_layers, latent_size, decoder_hidden_size) <= 0:
            raise ValueError("input, hidden, layer, and latent sizes must be positive")
        recurrent_dropout = dropout if num_layers > 1 else 0.0
        self.encoder = nn.LSTM(
            input_size,
            hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=recurrent_dropout,
        )
        self.to_latent = nn.Linear(hidden_size, latent_size)
        self.from_latent = nn.Linear(latent_size, decoder_hidden_size)
        self.decoder = nn.LSTM(
            decoder_hidden_size,
            decoder_hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=recurrent_dropout,
        )
        self.output = nn.Linear(decoder_hidden_size, input_size)

    def encode(self, values: torch.Tensor) -> torch.Tensor:
        """Return the latent vector for a batch of (batch, time, channel) windows."""
        _, (hidden, _) = self.encoder(values)
        return self.to_latent(hidden[-1])

    def forward(self, values: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Return latent vectors and reconstructed input windows."""
        latent = self.encode(values)
        repeated = self.from_latent(latent).unsqueeze(1).expand(-1, values.size(1), -1)
        decoded, _ = self.decoder(repeated)
        return latent, self.output(decoded)


class HealthRULModel(nn.Module):
    """Use a frozen or fine-tuned autoencoder representation plus HI to estimate RUL."""

    def __init__(self, autoencoder: SequenceAutoencoder, hidden_size: int = 64) -> None:
        """Attach an MLP that consumes latent features and one HI value."""
        super().__init__()
        self.autoencoder = autoencoder
        self.rul_head = nn.Sequential(
            nn.Linear(autoencoder.to_latent.out_features + 1, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_size, 1),
        )

    def forward(
        self, values: torch.Tensor, healthy_error_mean: torch.Tensor,
        healthy_error_std: torch.Tensor, healthy_hi_mean: float,
        healthy_hi_std: float,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Return scaled RUL, latent, per-channel z drift, and scalar health index."""
        latent, reconstruction = self.autoencoder(values)
        channel_error = (reconstruction - values).square().mean(dim=1)
        drift = (channel_error - healthy_error_mean) / healthy_error_std.clamp_min(1e-6)
        hi = drift.mean(dim=1, keepdim=True)
        normalized_hi = (hi - healthy_hi_mean) / max(healthy_hi_std, 1e-6)
        prediction = self.rul_head(torch.cat((latent, normalized_hi), dim=1))
        return prediction, latent, drift, hi


def build_autoencoder(input_size: int, config: dict[str, Any]) -> SequenceAutoencoder:
    """Construct the sequence autoencoder from YAML settings."""
    return SequenceAutoencoder(
        input_size=input_size,
        hidden_size=int(config["encoder_hidden_size"]),
        num_layers=int(config["encoder_layers"]),
        latent_size=int(config["latent_size"]),
        decoder_hidden_size=int(config["decoder_hidden_size"]),
        dropout=float(config["dropout"]),
    )
