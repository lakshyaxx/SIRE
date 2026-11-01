"""Load, validate, and label NASA C-MAPSS data files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import RAW_COLUMNS, cmapss_root, get_dataset_spec


@dataclass
class CMapssData:
    """Parsed train/test frames and official test RUL labels for one subset."""

    dataset: str
    train: pd.DataFrame
    test: pd.DataFrame
    test_truth: pd.DataFrame


def _read_sensor_frame(path: Path) -> pd.DataFrame:
    """Read one headerless whitespace-separated file and enforce its schema."""
    frame = pd.read_csv(path, sep=r"\s+", header=None, engine="python")
    frame = frame.dropna(axis=1, how="all")
    if frame.shape[1] != len(RAW_COLUMNS):
        raise ValueError(f"{path.name}: expected 26 columns, found {frame.shape[1]}")
    frame.columns = RAW_COLUMNS
    if frame.isna().any().any():
        columns = frame.columns[frame.isna().any()].tolist()
        raise ValueError(f"{path.name}: missing values in columns {columns}")
    if not np.isfinite(frame.to_numpy(dtype=np.float64)).all():
        raise ValueError(f"{path.name}: non-finite values found")
    if (frame["cycle"] < 1).any() or (frame["unit"] < 1).any():
        raise ValueError(f"{path.name}: unit and cycle identifiers must be positive")
    if frame.duplicated(["unit", "cycle"]).any():
        raise ValueError(f"{path.name}: duplicate (unit, cycle) rows found")
    return frame


def load_cmapss_dataset(
    dataset: str,
    data_dir: str | Path | None = None,
    rul_cap: int = 125,
) -> CMapssData:
    """Load raw frames, derive train RUL labels, and align official test labels."""
    if rul_cap <= 0:
        raise ValueError("rul_cap must be positive")
    spec = get_dataset_spec(dataset)
    folder = Path(data_dir) if data_dir is not None else cmapss_root() / "data"
    train = _read_sensor_frame(folder / spec.train_filename)
    test = _read_sensor_frame(folder / spec.test_filename)
    rul_frame = pd.read_csv(folder / spec.rul_filename, sep=r"\s+", header=None, engine="python")
    rul_frame = rul_frame.dropna(axis=1, how="all")
    if rul_frame.shape[1] != 1:
        raise ValueError(f"{spec.rul_filename}: expected one RUL value per row, found {rul_frame.shape[1]} columns")
    raw_test_rul = pd.to_numeric(rul_frame.iloc[:, 0], errors="raise").to_numpy(dtype=np.float64)
    if not np.isfinite(raw_test_rul).all() or (raw_test_rul < 0).any():
        raise ValueError(f"{spec.rul_filename}: RUL values must be finite and non-negative")

    train_units = set(train["unit"].astype(int).unique())
    test_units = sorted(test["unit"].astype(int).unique().tolist())
    if train_units != set(range(1, len(train_units) + 1)):
        raise ValueError(f"{spec.train_filename}: engine ids must be contiguous from 1")
    if test_units != list(range(1, len(test_units) + 1)):
        raise ValueError(f"{spec.test_filename}: engine ids must be contiguous from 1 for official RUL row alignment")
    if len(raw_test_rul) != len(test_units):
        raise ValueError(
            f"{spec.rul_filename}: {len(raw_test_rul)} RUL rows do not match {len(test_units)} test engines"
        )

    max_cycle = train.groupby("unit", sort=False)["cycle"].transform("max")
    train = train.copy()
    train["rul_raw"] = (max_cycle - train["cycle"]).astype(np.float64)
    train["rul_clipped"] = train["rul_raw"].clip(upper=float(rul_cap))
    test_truth = pd.DataFrame(
        {
            "unit": test_units,
            "rul_raw": raw_test_rul,
            "rul_clipped": np.minimum(raw_test_rul, float(rul_cap)),
        }
    )
    return CMapssData(spec.dataset, train, test, test_truth)


def load_train(path: str | Path, rul_cap: int = 125) -> pd.DataFrame:
    """Read a training file and compute raw and clipped RUL columns."""
    if rul_cap <= 0:
        raise ValueError("rul_cap must be positive")
    frame = _read_sensor_frame(Path(path))
    maximum = frame.groupby("unit")["cycle"].transform("max")
    frame["rul_raw"] = (maximum - frame["cycle"]).astype(float)
    frame["rul_clipped"] = frame["rul_raw"].clip(upper=float(rul_cap))
    return frame


def load_test(path: str | Path) -> pd.DataFrame:
    """Read and validate a raw test sensor file."""
    return _read_sensor_frame(Path(path))


def load_official_rul(path: str | Path) -> np.ndarray:
    """Read a one-column official RUL file as a finite non-negative vector."""
    frame = pd.read_csv(path, sep=r"\s+", header=None, engine="python").dropna(axis=1, how="all")
    if frame.shape[1] != 1:
        raise ValueError(f"{Path(path).name}: expected one RUL value per row, found {frame.shape[1]} columns")
    values = pd.to_numeric(frame.iloc[:, 0], errors="raise").to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError(f"{Path(path).name}: RUL values must be finite and non-negative")
    return values
