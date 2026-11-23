"""LightGBM regression model for remaining useful life."""
from pathlib import Path

import lightgbm as lgb
import numpy as np

from .base import BaseModel


class LightGBMRULRegressor(BaseModel):
    """LightGBM regressor with stable seeded training and native persistence."""
    def __init__(self, **params) -> None:
        self.params = {"objective": "regression", "verbosity": -1, "n_jobs": -1, **params}
        self.model = lgb.LGBMRegressor(**self.params)

    def fit(self, x, y, **kwargs) -> "LightGBMRULRegressor":
        self.model.fit(x, y, **kwargs)
        return self

    def predict(self, x) -> np.ndarray:
        """Predict nonnegative RUL values."""
        return np.maximum(self.model.predict(x), 0.0)

    def save(self, path: str | Path) -> None:
        """Write model in LightGBM's native text format."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.model.booster_.save_model(str(path))

    @classmethod
    def load(cls, path: str | Path, params: dict | None = None) -> "LightGBMRULRegressor":
        """Load a saved native LightGBM model."""
        instance = cls(**(params or {}))
        instance.model = lgb.LGBMRegressor(**instance.params)
        instance.model._Booster = lgb.Booster(model_file=str(path))
        instance.model._n_features = instance.model._Booster.num_feature()
        instance.model.fitted_ = True
        return instance
