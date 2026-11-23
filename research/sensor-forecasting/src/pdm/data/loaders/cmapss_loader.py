"""Read the space-separated C-MAPSS FD001-FD004 files."""
from pathlib import Path

import pandas as pd

from .base_loader import BaseLoader

SETTING_COLUMNS = [f"setting_{i}" for i in range(1, 4)]
SENSOR_COLUMNS = [f"sensor_{i}" for i in range(1, 22)]
COLUMNS = ["unit", "cycle", *SETTING_COLUMNS, *SENSOR_COLUMNS]


class CMapssLoader(BaseLoader):
    """Load official C-MAPSS text files into consistently named dataframes."""

    def _read_table(self, filename: str) -> pd.DataFrame:
        path = self.raw_dir / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        frame = pd.read_csv(path, sep=r"\s+", header=None, names=COLUMNS, usecols=range(26))
        frame[["unit", "cycle"]] = frame[["unit", "cycle"]].astype("int64")
        return frame

    @staticmethod
    def _validate_subset(subset: str) -> str:
        normalized = subset.upper()
        if normalized not in {f"FD{i:03}" for i in range(1, 5)}:
            raise ValueError(f"Unsupported C-MAPSS subset: {subset}")
        return normalized

    def load_train(self, subset: str) -> pd.DataFrame:
        """Load complete run-to-failure trajectories."""
        return self._read_table(f"train_{self._validate_subset(subset)}.txt")

    def load_test(self, subset: str) -> tuple[pd.DataFrame, pd.Series]:
        """Load truncated trajectories and official final-cycle RUL values."""
        subset = self._validate_subset(subset)
        trajectories = self._read_table(f"test_{subset}.txt")
        rul_path = self.raw_dir / f"RUL_{subset}.txt"
        if not rul_path.is_file():
            raise FileNotFoundError(rul_path)
        rul = pd.read_csv(rul_path, sep=r"\s+", header=None).iloc[:, 0]
        rul.index = pd.Index(range(1, len(rul) + 1), name="unit")
        if len(rul) != trajectories["unit"].nunique():
            raise ValueError(f"{rul_path.name} count does not match test engine count")
        rul.name = "rul"
        return trajectories, rul
