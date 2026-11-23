"""Common interface for predictive maintenance dataset loaders."""
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class BaseLoader(ABC):
    """Base class for loaders returning normalized C-MAPSS style tables."""

    def __init__(self, raw_dir: str | Path) -> None:
        self.raw_dir = Path(raw_dir)

    @abstractmethod
    def load_train(self, subset: str) -> pd.DataFrame:
        """Load labeled training trajectories."""

    @abstractmethod
    def load_test(self, subset: str) -> tuple[pd.DataFrame, pd.Series]:
        """Load truncated test trajectories and their engine-level RUL targets."""
