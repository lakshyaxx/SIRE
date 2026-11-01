"""Dataset registry and shared CMAPSS protocol defaults."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATASET_IDS = ("FD001", "FD002", "FD003", "FD004")
RAW_COLUMNS = ("unit", "cycle", "op1", "op2", "op3", *(f"s{i}" for i in range(1, 22)))
SETTING_COLUMNS = ("op1", "op2", "op3")
SENSOR_COLUMNS = tuple(f"s{i}" for i in range(1, 22))


@dataclass(frozen=True)
class DatasetSpec:
    """Files and operating-condition metadata for one C-MAPSS subset."""

    dataset: str
    n_conditions: int

    @property
    def train_filename(self) -> str:
        """Return the training filename for this subset."""
        return f"train_{self.dataset}.txt"

    @property
    def test_filename(self) -> str:
        """Return the test filename for this subset."""
        return f"test_{self.dataset}.txt"

    @property
    def rul_filename(self) -> str:
        """Return the official test RUL filename for this subset."""
        return f"RUL_{self.dataset}.txt"


DATASETS = {
    dataset: DatasetSpec(dataset, 6 if dataset in {"FD002", "FD004"} else 1)
    for dataset in DATASET_IDS
}


@dataclass(frozen=True)
class CMapssConfig:
    """Shared run settings; model-specific hyperparameters belong in model YAML."""

    rul_cap: int = 125
    window_length: int = 30
    stride: int = 1
    val_fraction: float = 0.2
    seed: int = 42
    batch_size: int = 256
    num_workers: int = 0

    def __post_init__(self) -> None:
        if self.rul_cap <= 0 or self.window_length <= 0 or self.stride <= 0:
            raise ValueError("rul_cap, window_length, and stride must be positive")
        if not 0.0 < self.val_fraction < 1.0:
            raise ValueError("val_fraction must be between 0 and 1")
        if self.batch_size <= 0 or self.num_workers < 0:
            raise ValueError("batch_size must be positive and num_workers non-negative")


def get_dataset_spec(dataset: str) -> DatasetSpec:
    """Return the registry entry for a subset, case-insensitively."""
    normalized = dataset.upper()
    try:
        return DATASETS[normalized]
    except KeyError as exc:
        raise ValueError(f"Unknown C-MAPSS dataset {dataset!r}; expected one of {DATASET_IDS}") from exc


def cmapss_root() -> Path:
    """Resolve the CMAPSS track root independently of the working directory."""
    return Path(__file__).resolve().parents[1]
