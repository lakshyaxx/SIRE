"""Validation helpers for C-MAPSS sensor tables."""
import numpy as np
import pandas as pd

from .loaders.cmapss_loader import COLUMNS


def validate_cmapss(frame: pd.DataFrame, *, require_complete: bool = True) -> None:
    """Raise ValueError when a C-MAPSS table violates its schema or cycle contract."""
    missing = set(COLUMNS).difference(frame.columns)
    if missing:
        raise ValueError(f"Missing C-MAPSS columns: {sorted(missing)}")
    values = frame[COLUMNS]
    if values.isna().any().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("C-MAPSS values must be finite and non-missing")
    if (frame[["unit", "cycle"]] < 1).any().any():
        raise ValueError("Unit and cycle identifiers must be positive")
    if frame.duplicated(["unit", "cycle"]).any():
        raise ValueError("Duplicate unit/cycle rows found")
    for _, group in frame.groupby("unit", sort=False):
        cycles = group["cycle"].to_numpy()
        if require_complete and not np.array_equal(cycles, np.arange(1, len(cycles) + 1)):
            raise ValueError("Cycles must be contiguous and start at 1 for each engine")
        if not require_complete and (np.diff(cycles) <= 0).any():
            raise ValueError("Cycles must be strictly increasing for each engine")
