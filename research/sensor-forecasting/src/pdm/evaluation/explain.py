"""Model feature importance utilities for the LightGBM baseline."""
from pathlib import Path

import pandas as pd

from pdm.models.lightgbm_model import LightGBMRULRegressor


def feature_importance(model_path: str | Path, feature_names: list[str]) -> pd.DataFrame:
    """Return gain and split importance for a saved LightGBM booster."""
    import lightgbm as lgb
    booster = lgb.Booster(model_file=str(model_path))
    return pd.DataFrame({"feature": feature_names,
                         "gain": booster.feature_importance(importance_type="gain"),
                         "split": booster.feature_importance(importance_type="split")}).sort_values("gain", ascending=False)


def shap_values(model_path: str | Path, samples: pd.DataFrame):
    """Compute SHAP values lazily for a bounded sample of engineered features."""
    import lightgbm as lgb
    import shap
    booster = lgb.Booster(model_file=str(model_path))
    return shap.TreeExplainer(booster).shap_values(samples)
