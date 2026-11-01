"""Deterministic training helper and checkpoint tests."""

import numpy as np
import pandas as pd
import torch
from torch.utils.data import TensorDataset

from common.train_utils import EarlyStopping, make_data_loader, seed_everything, train_deep_model


def test_early_stopping_tracks_best_and_patience() -> None:
    """Stop only after the configured number of non-improving epochs."""
    stopping = EarlyStopping(patience=2)
    assert stopping.update(3.0, 1) is False
    assert stopping.update(2.0, 2) is False
    assert stopping.update(2.5, 3) is False
    assert stopping.update(2.7, 4) is True
    assert stopping.best_epoch == 2


def test_train_model_saves_history_and_best_checkpoint(tmp_path) -> None:
    """Run a short real CPU training loop and persist its outputs."""
    seed_everything(42)
    x = torch.tensor([[0.0], [1.0], [2.0], [3.0]], dtype=torch.float32)
    y = torch.tensor([0.0, 1.0, 2.0, 3.0], dtype=torch.float32)
    dataset = TensorDataset(x, y)
    train_loader = make_data_loader(dataset, batch_size=2, shuffle=True, device="cpu")
    val_loader = make_data_loader(dataset, batch_size=2, shuffle=False, device="cpu")
    model = torch.nn.Linear(1, 1)
    history = train_deep_model(
        model,
        train_loader,
        val_loader,
        tmp_path,
        rul_cap=5.0,
        max_epochs=2,
        patience=2,
        device="cpu",
    )
    assert list(history.columns) == ["epoch", "train_loss", "val_loss", "val_rmse", "lr", "seconds"]
    assert len(history) == 2
    assert (tmp_path / "best_model.pt").is_file()
    assert pd.read_csv(tmp_path / "history.csv").shape[0] == 2
