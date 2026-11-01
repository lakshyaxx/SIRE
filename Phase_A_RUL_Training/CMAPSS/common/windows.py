"""Causal fixed-length window generation with repeated-first-row padding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset


@dataclass
class WindowSet:
    """Window tensor and row-level target/engine metadata."""

    x: np.ndarray
    y: np.ndarray | None
    units: np.ndarray
    steps: np.ndarray
    padded_engines: int = 0
    y_raw: np.ndarray | None = None
    condition_ids: np.ndarray | None = None

    def __len__(self) -> int:
        """Return the number of generated windows."""
        return int(self.x.shape[0])


def _padded_window(values: np.ndarray, end_index: int, length: int) -> tuple[np.ndarray, bool]:
    """Build a window ending at a row and repeat the first available row on the left."""
    start = max(0, end_index - length + 1)
    window = values[start : end_index + 1]
    padded = window.shape[0] < length
    if padded:
        padding = np.repeat(window[:1], length - window.shape[0], axis=0)
        window = np.concatenate([padding, window], axis=0)
    return window, padded


def make_windows(
    frame: pd.DataFrame,
    feature_columns: Sequence[str],
    window_length: int = 30,
    stride: int = 1,
    target_column: str | None = "rul_clipped",
) -> WindowSet:
    """Create one causal window per stride endpoint, grouped and ordered by engine."""
    if window_length <= 0 or stride <= 0:
        raise ValueError("window_length and stride must be positive")
    required = {"unit", "cycle", *feature_columns}
    if target_column is not None:
        required.add(target_column)
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Window frame is missing required columns: {sorted(missing)}")
    ordered = frame.sort_values(["unit", "cycle"], kind="stable")
    windows: list[np.ndarray] = []
    targets: list[float] = []
    raw_targets: list[float] = []
    conditions: list[int] = []
    units: list[int] = []
    steps: list[int] = []
    padded_engine_count = 0
    for unit, group in ordered.groupby("unit", sort=True):
        values = group[list(feature_columns)].to_numpy(dtype=np.float32)
        padded_engine_count += int(len(group) < window_length)
        unit_steps = group["cycle"].to_numpy(dtype=np.int64)
        target_values = group[target_column].to_numpy(dtype=float) if target_column else None
        raw_values = group["rul_raw"].to_numpy(dtype=float) if target_column and "rul_raw" in group else None
        condition_values = group["condition_id"].to_numpy(dtype=np.int64) if "condition_id" in group else None
        for end_index in range(0, len(group), stride):
            window, _ = _padded_window(values, end_index, window_length)
            windows.append(window)
            units.append(int(unit))
            steps.append(int(unit_steps[end_index]))
            if target_values is not None:
                targets.append(float(target_values[end_index]))
            if raw_values is not None:
                raw_targets.append(float(raw_values[end_index]))
            if condition_values is not None:
                conditions.append(int(condition_values[end_index]))
    x = np.stack(windows).astype(np.float32, copy=False) if windows else np.empty((0, window_length, len(feature_columns)), dtype=np.float32)
    y = np.asarray(targets, dtype=np.float32) if target_column is not None else None
    y_raw = np.asarray(raw_targets, dtype=np.float32) if raw_targets else None
    condition_ids = np.asarray(conditions, dtype=np.int64) if conditions else None
    return WindowSet(x, y, np.asarray(units, dtype=np.int64), np.asarray(steps, dtype=np.int64), padded_engine_count, y_raw, condition_ids)


def make_test_last_windows(
    frame: pd.DataFrame,
    feature_columns: Sequence[str],
    window_length: int = 30,
) -> WindowSet:
    """Create one final-cycle window for each test engine, counting padded engines."""
    if window_length <= 0:
        raise ValueError("window_length must be positive")
    required = {"unit", "cycle", *feature_columns}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Test frame is missing required columns: {sorted(missing)}")
    ordered = frame.sort_values(["unit", "cycle"], kind="stable")
    windows: list[np.ndarray] = []
    units: list[int] = []
    steps: list[int] = []
    conditions: list[int] = []
    padded = 0
    for unit, group in ordered.groupby("unit", sort=True):
        values = group[list(feature_columns)].to_numpy(dtype=np.float32)
        window, did_pad = _padded_window(values, len(values) - 1, window_length)
        windows.append(window)
        units.append(int(unit))
        steps.append(int(group["cycle"].iloc[-1]))
        if "condition_id" in group:
            conditions.append(int(group["condition_id"].iloc[-1]))
        padded += int(did_pad)
    x = np.stack(windows).astype(np.float32, copy=False) if windows else np.empty((0, window_length, len(feature_columns)), dtype=np.float32)
    condition_ids = np.asarray(conditions, dtype=np.int64) if conditions else None
    return WindowSet(x, None, np.asarray(units, dtype=np.int64), np.asarray(steps, dtype=np.int64), padded, condition_ids=condition_ids)


class WindowDataset(Dataset[tuple[torch.Tensor, torch.Tensor] | torch.Tensor]):
    """PyTorch dataset wrapper for generated windows and optional targets."""

    def __init__(self, windows: WindowSet) -> None:
        self.windows = windows

    def __len__(self) -> int:
        """Return the number of samples."""
        return len(self.windows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor] | torch.Tensor:
        """Return float tensors for one input window and its target, if present."""
        x = torch.from_numpy(self.windows.x[index])
        if self.windows.y is None:
            return x
        return x, torch.tensor(self.windows.y[index], dtype=torch.float32)
