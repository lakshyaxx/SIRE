"""Reusable raw-history preprocessing and prediction contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd

from .config import RAW_COLUMNS
from .preprocess import CMapssPreprocessor


class PredictorBase(ABC):
    """Base for model-specific predictors that accept raw one-engine history."""

    def __init__(
        self,
        preprocessor: CMapssPreprocessor,
        model: str,
        dataset: str,
        seed: int,
        version: str,
        window_length: int = 30,
    ) -> None:
        if window_length <= 0:
            raise ValueError("window_length must be positive")
        self.preprocessor = preprocessor
        self.model = model
        self.dataset = dataset.upper()
        self.seed = int(seed)
        self.version = version
        self.window_length = window_length

    @abstractmethod
    def predict_window(self, window: np.ndarray) -> tuple[float, dict[str, Any]]:
        """Predict RUL from a normalized `(1, L, F)` window and return extras."""

    def prepare_window(self, history: pd.DataFrame) -> tuple[np.ndarray, int, list[str]]:
        """Validate raw rows, preprocess them, and build the latest padded window."""
        if not isinstance(history, pd.DataFrame) or history.empty:
            raise ValueError("history must be a non-empty pandas DataFrame")
        required = set(RAW_COLUMNS) - {"unit"}
        missing = required - set(history.columns)
        if missing:
            raise ValueError(f"History is missing required raw columns: {sorted(missing)}")
        raw = history.copy()
        if "unit" not in raw:
            raw["unit"] = 1
        if raw["unit"].nunique() != 1:
            raise ValueError("history must contain rows for exactly one engine")
        raw = raw.sort_values("cycle", kind="stable")
        if raw["cycle"].duplicated().any() or (raw["cycle"] < 1).any():
            raise ValueError("history cycle values must be unique positive integers")
        numeric = raw[list(RAW_COLUMNS)].to_numpy(dtype=float)
        if not np.isfinite(numeric).all():
            raise ValueError("history contains missing or non-finite raw values")
        normalized = self.preprocessor.transform(raw)
        channels = normalized[list(self.preprocessor.feature_columns)].to_numpy(dtype=np.float32)
        used = min(len(channels), self.window_length)
        selected = channels[-self.window_length :]
        warnings: list[str] = []
        if len(channels) < self.window_length:
            pad_count = self.window_length - len(channels)
            selected = np.concatenate([np.repeat(channels[:1], pad_count, axis=0), channels], axis=0)
            warnings.append(f"History has {len(channels)} cycles; left-padded by repeating the first observation.")
        elif len(channels) > self.window_length:
            warnings.append(f"Used the latest {self.window_length} of {len(channels)} available cycles.")
        return selected[None, :, :], used, warnings

    def predict_rul(self, history: pd.DataFrame) -> dict[str, Any]:
        """Predict RUL for a raw engine history using the Phase A output contract."""
        window, used, warnings = self.prepare_window(history)
        prediction, extras = self.predict_window(window)
        result: dict[str, Any] = {
            "rul": float(prediction),
            "rul_unit": "cycles",
            "n_steps_used": int(used),
            "model": self.model,
            "dataset": self.dataset,
            "seed": self.seed,
            "version": self.version,
            "warnings": warnings,
        }
        result.update(extras)
        return result
