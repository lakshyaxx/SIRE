"""Regression metrics for C-MAPSS RUL prediction."""
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error


def nasa_score(y_true, y_pred) -> float:
    """Compute standard C-MAPSS asymmetric exponential penalty; lower is better."""
    error = np.asarray(y_pred, dtype=float) - np.asarray(y_true, dtype=float)
    penalties = np.where(error < 0, np.expm1(-error / 13.0), np.expm1(error / 10.0))
    return float(penalties.sum())


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    """Return MAE, RMSE, and NASA score for aligned RUL arrays."""
    truth, pred = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    if truth.shape != pred.shape or truth.size == 0:
        raise ValueError("truth and prediction arrays must be nonempty and have equal shapes")
    return {"mae": float(np.abs(truth - pred).mean()),
            "rmse": float(np.mean((truth - pred) ** 2) ** 0.5),
            "nasa_score": nasa_score(truth, pred)}
