"""Construct models from configuration names."""
from .lightgbm_model import LightGBMRULRegressor


def create_model(name: str, params: dict | None = None):
    """Instantiate a supported model by its configured name."""
    if name.lower() in {"lightgbm", "lgbm"}:
        return LightGBMRULRegressor(**(params or {}))
    raise ValueError(f"Unsupported model: {name}")
