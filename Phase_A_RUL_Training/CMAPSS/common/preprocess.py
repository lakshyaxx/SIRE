"""Train-only sensor filtering and operating-condition-aware scaling."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from .config import SENSOR_COLUMNS, SETTING_COLUMNS, cmapss_root, get_dataset_spec


@dataclass
class CMapssPreprocessor:
    """Serializable preprocessor fitted exclusively on training-engine rows."""

    dataset: str
    sensor_columns: tuple[str, ...] = SENSOR_COLUMNS
    setting_columns: tuple[str, ...] = SETTING_COLUMNS
    dropped_sensors: tuple[str, ...] = ()
    n_conditions: int = 1
    condition_scaler: StandardScaler | None = None
    clusterer: KMeans | None = None
    global_sensor_stats: dict[str, tuple[float, float]] = field(default_factory=dict)
    cluster_sensor_stats: dict[int, dict[str, tuple[float, float]]] = field(default_factory=dict)
    fitted_train_units: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        """Normalize the dataset id to the registry's canonical uppercase form."""
        self.dataset = self.dataset.upper()

    @property
    def kept_sensors(self) -> tuple[str, ...]:
        """Sensors that vary in the fitted training split."""
        return tuple(sensor for sensor in self.sensor_columns if sensor not in self.dropped_sensors)

    @property
    def feature_columns(self) -> tuple[str, ...]:
        """Ordered model inputs after normalization."""
        if self.n_conditions > 1:
            return (*self.kept_sensors, *self.setting_columns)
        return self.kept_sensors

    def fit(self, frame: pd.DataFrame, train_units: list[int] | tuple[int, ...]) -> "CMapssPreprocessor":
        """Fit feature statistics and clusters using only the supplied engine ids."""
        units = tuple(sorted({int(unit) for unit in train_units}))
        if not units:
            raise ValueError("train_units cannot be empty")
        missing = (set(self.sensor_columns) | set(self.setting_columns) | {"unit"}) - set(frame.columns)
        if missing:
            raise ValueError(f"Training frame is missing required columns: {sorted(missing)}")
        train = frame.loc[frame["unit"].astype(int).isin(units)].copy()
        if train.empty or set(train["unit"].astype(int).unique()) != set(units):
            raise ValueError("Every supplied training engine must have rows in the fit frame")
        self.n_conditions = get_dataset_spec(self.dataset).n_conditions
        self.fitted_train_units = units
        self.dropped_sensors = tuple(
            sensor for sensor in self.sensor_columns if train[sensor].nunique(dropna=False) <= 1
        )
        if self.n_conditions > 1:
            self.condition_scaler = StandardScaler().fit(train[list(self.setting_columns)])
            standardized_settings = self.condition_scaler.transform(train[list(self.setting_columns)])
            self.clusterer = KMeans(n_clusters=self.n_conditions, random_state=42, n_init=10)
            cluster_ids = self.clusterer.fit_predict(standardized_settings)
            self.cluster_sensor_stats = {}
            for cluster in range(self.n_conditions):
                cluster_rows = train.iloc[np.flatnonzero(cluster_ids == cluster)]
                self.cluster_sensor_stats[cluster] = {
                    sensor: self._mean_scale(cluster_rows[sensor].to_numpy(dtype=float))
                    for sensor in self.kept_sensors
                }
        else:
            self.global_sensor_stats = {
                sensor: self._mean_scale(train[sensor].to_numpy(dtype=float)) for sensor in self.kept_sensors
            }
        return self

    @staticmethod
    def _mean_scale(values: np.ndarray) -> tuple[float, float]:
        """Calculate population mean and a nonzero scale for one channel."""
        mean = float(np.mean(values))
        scale = float(np.std(values, ddof=0))
        return mean, scale if scale > 0 and np.isfinite(scale) else 1.0

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Apply the fitted sensor normalization and return model-ready rows."""
        if not self.fitted_train_units:
            raise RuntimeError("Preprocessor must be fitted before transform")
        required = set(self.sensor_columns) | {"unit", "cycle"}
        if self.n_conditions > 1:
            required.update(self.setting_columns)
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"Input frame is missing required columns: {sorted(missing)}")
        transformed = frame.copy()
        if self.n_conditions > 1:
            if self.condition_scaler is None or self.clusterer is None:
                raise RuntimeError("Condition scaler and clusterer are not fitted")
            # Within-cluster z-scores are floating point even when the raw file
            # parsed a sensor column as int64. Cast before assignment so recent
            # pandas versions do not silently change or reject the column dtype.
            transformed = transformed.astype(
                {sensor: np.float64 for sensor in self.sensor_columns}
            )
            scaled_settings = self.condition_scaler.transform(frame[list(self.setting_columns)])
            cluster_ids = self.clusterer.predict(scaled_settings)
            transformed["condition_id"] = cluster_ids.astype(np.int64)
            for cluster in range(self.n_conditions):
                mask = cluster_ids == cluster
                stats = self.cluster_sensor_stats[cluster]
                for sensor, (mean, scale) in stats.items():
                    transformed.loc[mask, sensor] = (frame.loc[mask, sensor] - mean) / scale
            transformed.loc[:, list(self.setting_columns)] = scaled_settings
        else:
            for sensor, (mean, scale) in self.global_sensor_stats.items():
                transformed[sensor] = (frame[sensor] - mean) / scale
            transformed["condition_id"] = 0
        return transformed

    def fit_transform(self, frame: pd.DataFrame, train_units: list[int] | tuple[int, ...]) -> pd.DataFrame:
        """Fit on selected engines, then transform the full frame."""
        return self.fit(frame, train_units).transform(frame)

    def save(self, path: str | Path | None = None) -> Path:
        """Persist this fitted preprocessor for training and inference reuse."""
        if not self.fitted_train_units:
            raise RuntimeError("Cannot save an unfitted preprocessor")
        target = Path(path) if path is not None else cmapss_root() / "results" / "artifacts" / self.dataset / "preprocessor.joblib"
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, target)
        return target


def load_preprocessor(path: str | Path) -> CMapssPreprocessor:
    """Load a saved fitted CMAPSS preprocessor."""
    result: Any = joblib.load(Path(path))
    if not isinstance(result, CMapssPreprocessor):
        raise TypeError(f"Artifact at {path} is not a CMapssPreprocessor")
    return result
