"""Reproducibility, device selection, and shared PyTorch training helpers."""

from __future__ import annotations

import copy
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from .metrics import rmse

LOG = logging.getLogger(__name__)


def seed_everything(seed: int = 42) -> None:
    """Seed Python, NumPy, and PyTorch generators for reproducible runs."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def select_device(device: str | torch.device | None = None) -> torch.device:
    """Select CUDA when available; otherwise log a visible CPU fallback warning."""
    if device is not None and str(device).lower() != "auto":
        selected = torch.device(device)
        if selected.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
    elif torch.cuda.is_available():
        selected = torch.device("cuda")
    else:
        LOG.warning("CUDA is unavailable; using CPU for this training run")
        selected = torch.device("cpu")
    if selected.type == "cuda":
        LOG.info("Using CUDA device: %s", torch.cuda.get_device_name(selected))
    else:
        LOG.info("Using device: %s", selected)
    return selected


def make_data_loader(
    dataset: Dataset[Any],
    batch_size: int = 256,
    shuffle: bool = False,
    num_workers: int = 0,
    seed: int = 42,
    device: str | torch.device = "cpu",
) -> DataLoader[Any]:
    """Construct a deterministically seeded loader with configurable workers."""
    if batch_size <= 0 or num_workers < 0:
        raise ValueError("batch_size must be positive and num_workers non-negative")
    generator = torch.Generator()
    generator.manual_seed(seed)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=torch.device(device).type == "cuda",
        generator=generator,
    )


@dataclass
class EarlyStopping:
    """Track validation improvements and indicate when patience is exhausted."""

    patience: int = 20
    min_delta: float = 0.0
    best: float = float("inf")
    best_epoch: int = 0
    bad_epochs: int = 0

    def update(self, value: float, epoch: int) -> bool:
        """Record an improvement and return whether training should stop."""
        if value < self.best - self.min_delta:
            self.best = float(value)
            self.best_epoch = int(epoch)
            self.bad_epochs = 0
        else:
            self.bad_epochs += 1
        return self.bad_epochs >= self.patience


def _unpack_batch(batch: Any, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    """Move a `(features, targets)` batch to the selected device."""
    if not isinstance(batch, (tuple, list)) or len(batch) != 2:
        raise TypeError("training and validation loaders must return (features, targets) batches")
    x, y = batch
    return x.to(device, non_blocking=True), y.to(device, non_blocking=True).reshape(-1, 1)


@torch.no_grad()
def _validation_rmse(model: nn.Module, loader: DataLoader[Any], device: torch.device, rul_cap: float) -> tuple[float, float]:
    """Return validation MSE in scaled units and RMSE in real RUL units."""
    model.eval()
    truth: list[np.ndarray] = []
    pred: list[np.ndarray] = []
    scaled_losses: list[float] = []
    for batch in loader:
        x, y = _unpack_batch(batch, device)
        output = model(x).reshape(-1, 1)
        scaled_target = y / rul_cap
        scaled_losses.append(float(nn.functional.mse_loss(output, scaled_target).item()))
        truth.append(y.detach().cpu().numpy().reshape(-1))
        pred.append((output * rul_cap).detach().cpu().numpy().reshape(-1))
    if not truth:
        raise ValueError("validation loader yielded no batches")
    return float(np.mean(scaled_losses)), rmse(np.concatenate(truth), np.concatenate(pred))


def train_deep_model(
    model: nn.Module,
    train_loader: DataLoader[Any],
    val_loader: DataLoader[Any],
    output_dir: str | Path,
    rul_cap: float = 125.0,
    seed: int = 42,
    device: str | torch.device | None = None,
    learning_rate: float = 1e-3,
    weight_decay: float = 1e-4,
    max_epochs: int = 150,
    patience: int = 20,
    scheduler_patience: int = 5,
    scheduler_factor: float = 0.5,
    gradient_clip: float = 1.0,
) -> pd.DataFrame:
    """Train an RUL network with AdamW, plateau scheduling, clipping and best restore."""
    if rul_cap <= 0 or max_epochs <= 0 or patience <= 0:
        raise ValueError("rul_cap, max_epochs and patience must be positive")
    seed_everything(seed)
    selected_device = select_device(device)
    model = model.to(selected_device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=scheduler_factor, patience=scheduler_patience
    )
    stopping = EarlyStopping(patience=patience)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / "best_model.pt"
    best_state: dict[str, torch.Tensor] | None = None
    history: list[dict[str, float | int]] = []

    for epoch in range(1, max_epochs + 1):
        started = time.perf_counter()
        model.train()
        losses: list[float] = []
        for batch in train_loader:
            x, y = _unpack_batch(batch, selected_device)
            target = y / rul_cap
            optimizer.zero_grad(set_to_none=True)
            prediction = model(x).reshape(-1, 1)
            loss = nn.functional.mse_loss(prediction, target)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), gradient_clip)
            optimizer.step()
            losses.append(float(loss.detach().item()))
        if not losses:
            raise ValueError("training loader yielded no batches")
        val_loss, val_rmse = _validation_rmse(model, val_loader, selected_device, rul_cap)
        scheduler.step(val_rmse)
        if val_rmse < stopping.best:
            best_state = copy.deepcopy(model.state_dict())
            torch.save(best_state, checkpoint)
        should_stop = stopping.update(val_rmse, epoch)
        row = {
            "epoch": epoch,
            "train_loss": float(np.mean(losses)),
            "val_loss": val_loss,
            "val_rmse": val_rmse,
            "lr": float(optimizer.param_groups[0]["lr"]),
            "seconds": time.perf_counter() - started,
        }
        history.append(row)
        LOG.info(
            "epoch=%d train_loss=%.6f val_rmse=%.4f lr=%.3g",
            epoch,
            row["train_loss"],
            val_rmse,
            row["lr"],
        )
        if should_stop:
            LOG.info("Early stopping at epoch %d; best epoch=%d val_rmse=%.4f", epoch, stopping.best_epoch, stopping.best)
            break
    if best_state is None:
        raise RuntimeError("Training completed without producing a best checkpoint")
    model.load_state_dict(best_state)
    history_frame = pd.DataFrame(history)
    history_frame.to_csv(output / "history.csv", index=False)
    return history_frame
