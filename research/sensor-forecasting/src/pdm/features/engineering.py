"""Convert per-cycle windows into compact tabular LightGBM features."""
import numpy as np
import pandas as pd


def window_features(windows: np.ndarray, feature_names: list[str]) -> pd.DataFrame:
    """Extract latest values, window mean/std, and linear trend per feature."""
    if windows.ndim != 3 or windows.shape[2] != len(feature_names):
        raise ValueError("windows must have shape (samples, time, len(feature_names))")
    n, length, _ = windows.shape
    latest = windows[:, -1, :]
    centered = np.arange(length, dtype=np.float32) - (length - 1) / 2
    denom = np.square(centered).sum()
    trends = np.einsum("t,ntf->nf", centered, windows) / denom if denom else np.zeros_like(latest)
    values = np.concatenate([latest, windows.mean(axis=1), windows.std(axis=1), trends], axis=1)
    columns = ([f"{name}_last" for name in feature_names] + [f"{name}_mean" for name in feature_names] +
               [f"{name}_std" for name in feature_names] + [f"{name}_trend" for name in feature_names])
    return pd.DataFrame(values, columns=columns, index=range(n))
