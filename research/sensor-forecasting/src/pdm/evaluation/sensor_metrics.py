"""Aligned sensor forecast scoring, independent of RUL metrics."""
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

METRICS = ["mae", "mse", "rmse", "r2", "mape", "smape"]


def score_sensor_forecast(actual: pd.DataFrame, forecast: pd.DataFrame) -> list[dict]:
    """Return per-target scores; percentages are on a 0–100 or 0–200 scale."""
    if (not len(actual) or not actual.index.equals(forecast.index)
            or not actual.columns.equals(forecast.columns)
            or not np.isfinite(actual.to_numpy()).all() or not np.isfinite(forecast.to_numpy()).all()):
        raise ValueError("Actuals and predictions must be finite and aligned by cycle and target")
    scores = []
    for target in actual:
        y, pred = actual[target].to_numpy(), forecast[target].to_numpy()
        error = np.abs(y - pred)
        denominator = np.abs(y) + np.abs(pred)
        mse = mean_squared_error(y, pred)
        scores.append({"target": target, "mae": mean_absolute_error(y, pred), "mse": mse,
                       "rmse": np.sqrt(mse), "r2": r2_score(y, pred) if len(y) > 1 and np.ptp(y) else None,
                       "mape": 100 * np.mean(error / np.abs(y)) if np.all(y != 0) else None,
                       "smape": 200 * np.divide(error, denominator, out=np.zeros_like(error),
                                                where=denominator != 0).mean()})
    return scores
