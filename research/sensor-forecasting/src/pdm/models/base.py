"""Shared interface for trainable predictive models."""
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np


class BaseModel(ABC):
    """Small fit/predict/save interface used by model implementations."""
    @abstractmethod
    def fit(self, x, y, **kwargs):
        """Fit the model."""

    @abstractmethod
    def predict(self, x) -> np.ndarray:
        """Return continuous predictions."""

    @abstractmethod
    def save(self, path: str | Path) -> None:
        """Persist the fitted model."""
