"""Health indicator calibration, onset detection, and prognostic quality metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def calibrate_health(
    reconstruction_errors: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Calibrate channel errors and HI using healthy validation-window population stats."""
    values = np.asarray(reconstruction_errors, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 2:
        raise ValueError("healthy reconstruction errors must have shape (n>=2, channels)")
    if not np.isfinite(values).all():
        raise ValueError("healthy reconstruction errors must be finite")
    means = values.mean(axis=0)
    stds = values.std(axis=0, ddof=0)
    safe_stds = np.maximum(stds, 1e-6)
    healthy_hi = ((values - means) / safe_stds).mean(axis=1)
    hi_mean = float(healthy_hi.mean())
    hi_std = float(healthy_hi.std(ddof=0))
    return means, safe_stds, hi_mean, max(hi_std, 1e-6)


def detect_onset(
    steps: np.ndarray, hi: np.ndarray, threshold: float, consecutive: int = 5
) -> int | None:
    """Return first cycle in a consecutive above-threshold HI run, else None."""
    cycles = np.asarray(steps, dtype=np.int64).reshape(-1)
    values = np.asarray(hi, dtype=np.float64).reshape(-1)
    if cycles.shape != values.shape:
        raise ValueError("steps and HI must have matching lengths")
    if consecutive <= 0:
        raise ValueError("consecutive must be positive")
    above = np.isfinite(values) & (values > threshold)
    if len(above) < consecutive:
        return None
    rolling = np.convolve(above.astype(int), np.ones(consecutive, dtype=int), mode="valid")
    locations = np.flatnonzero(rolling == consecutive)
    return int(cycles[locations[0]]) if len(locations) else None


def prognostic_quality(
    frame: pd.DataFrame,
    hi_column: str = "hi",
    truth_column: str = "rul_raw",
) -> dict[str, float | int]:
    """Measure HI quality: Spearman(HI,RUL), monotonicity, and trendability.

    Monotonicity per unit is (rising steps - falling steps) / all non-tied
    adjacent steps; ties are excluded and a fully tied unit scores zero.
    Trendability is the mean absolute Pearson correlation between HI and cycle
    index computed separately per unit (minimum three rows), with constants
    scored zero. Spearman correlation is pooled across rows.
    """
    correlation = spearmanr(frame[hi_column], frame[truth_column]).statistic
    monotonicity: list[float] = []
    trendability: list[float] = []
    for _, group in frame.groupby("unit", sort=False):
        ordered = group.sort_values("step", kind="stable")
        differences = np.diff(ordered[hi_column].to_numpy(dtype=float))
        nonzero = differences[differences != 0]
        monotonicity.append(
            float((np.sum(nonzero > 0) - np.sum(nonzero < 0)) / len(nonzero))
            if len(nonzero)
            else 0.0
        )
        if len(ordered) < 3:
            continue
        values = ordered[hi_column].to_numpy(dtype=float)
        cycles = ordered["step"].to_numpy(dtype=float)
        value_std = float(np.std(values))
        cycle_std = float(np.std(cycles))
        trendability.append(
            abs(float(np.corrcoef(values, cycles)[0, 1]))
            if value_std > 0 and cycle_std > 0
            else 0.0
        )
    return {
        "spearman_hi_rul": float(correlation) if np.isfinite(correlation) else 0.0,
        "mean_unit_monotonicity": float(np.mean(monotonicity)) if monotonicity else 0.0,
        "mean_unit_trendability": float(np.mean(trendability)) if trendability else 0.0,
        "units": int(frame["unit"].nunique()),
    }
