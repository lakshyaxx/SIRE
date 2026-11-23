"""Train-fitted C-MAPSS feature selection and scaling."""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler, StandardScaler

FEATURE_COLUMNS = [f"setting_{i}" for i in range(1, 4)] + [f"sensor_{i}" for i in range(1, 22)]


class CMapssPreprocessor:
    """Drop constant sensors and scale using training rows only."""

    def __init__(self, scaler: str = "minmax", per_condition: bool = False,
                 n_conditions: int = 6, seed: int = 42) -> None:
        if scaler not in {"minmax", "standard"}:
            raise ValueError("scaler must be 'minmax' or 'standard'")
        self.scaler_name = scaler
        self.per_condition = per_condition
        self.n_conditions = n_conditions
        self.seed = seed
        self.features: list[str] = []
        self.constant_features: list[str] = []
        self.scaler = None

    def fit(self, train: pd.DataFrame) -> "CMapssPreprocessor":
        """Fit feature selection and scaling on training data only."""
        self.constant_features = [c for c in FEATURE_COLUMNS if train[c].nunique(dropna=False) <= 1]
        self.features = [c for c in FEATURE_COLUMNS if c not in self.constant_features]
        self._train_values = train[self.features].copy()
        self.condition_stats = {}
        if self.per_condition:
            self.condition_scaler = StandardScaler().fit(train[["setting_1", "setting_2", "setting_3"]])
            settings = self.condition_scaler.transform(train[["setting_1", "setting_2", "setting_3"]])
            self.condition_model = KMeans(n_clusters=self.n_conditions, n_init=10,
                                          random_state=self.seed).fit(settings)
            self.train_condition_labels = self.condition_model.labels_
            for label in range(self.n_conditions):
                indices = (self.train_condition_labels == label).nonzero()[0]
                vals = train.iloc[indices][self.features]
                self.condition_stats[label] = (vals.mean(), vals.std().replace(0, 1).fillna(1))
        cls = MinMaxScaler if self.scaler_name == "minmax" else StandardScaler
        fit_values = train[self.features].astype("float64").copy()
        if self.per_condition:
            for label in range(self.n_conditions):
                indices = (self.train_condition_labels == label).nonzero()[0]
                mean, std = self.condition_stats[label]
                fit_values.iloc[indices] = (train.iloc[indices][self.features] - mean) / std
        self.scaler = cls().fit(fit_values)
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Transform features, optionally normalizing each operating condition."""
        if self.scaler is None:
            raise RuntimeError("Preprocessor must be fitted before transform")
        result = frame.copy()
        result[self.features] = result[self.features].astype("float64")
        if self.per_condition:
            settings = self.condition_scaler.transform(result[["setting_1", "setting_2", "setting_3"]])
            condition_labels = self.condition_model.predict(settings)
            fallback = (self._train_values.mean(), self._train_values.std().replace(0, 1).fillna(1))
            normalized = result[self.features].copy()
            for label in np.unique(condition_labels):
                indices = (condition_labels == label).nonzero()[0]
                mean, std = self.condition_stats.get(int(label), fallback)
                normalized.iloc[indices] = (result.iloc[indices][self.features] - mean) / std
            result[self.features] = normalized
        result[self.features] = self.scaler.transform(result[self.features])
        return result

    def fit_transform(self, train: pd.DataFrame) -> pd.DataFrame:
        """Fit on train and return its transformed copy."""
        self.fit(train)
        return self.transform(train)
