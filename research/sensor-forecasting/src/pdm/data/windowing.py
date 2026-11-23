"""Create cycle-ordered sliding windows without crossing engine boundaries."""
import numpy as np
import pandas as pd


def make_windows(frame: pd.DataFrame, feature_columns: list[str], window_size: int = 30,
                 stride: int = 1, target_column: str = "rul", pad_short: bool = True
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return windows, last-row targets and unit IDs, optionally left-padding short series."""
    if window_size < 1 or stride < 1:
        raise ValueError("window_size and stride must be positive")
    xs, ys, units = [], [], []
    for unit, group in frame.groupby("unit", sort=True):
        group = group.sort_values("cycle")
        values = group[feature_columns].to_numpy(dtype=np.float32)
        targets = group[target_column].to_numpy(dtype=np.float32) if target_column in group else None
        if len(values) < window_size and not pad_short:
            continue
        if len(values) < window_size:
            starts = [0]
        else:
            starts = list(range(0, len(values) - window_size + 1, stride))
            if starts[-1] != len(values) - window_size:
                starts.append(len(values) - window_size)
        for start in starts:
            end = min(start + window_size, len(values))
            window = values[start:end]
            if len(window) < window_size:
                window = np.pad(window, ((window_size - len(window), 0), (0, 0)), mode="edge")
            xs.append(window)
            if targets is not None:
                ys.append(targets[end - 1])
            units.append(unit)
    return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.float32), np.asarray(units)
