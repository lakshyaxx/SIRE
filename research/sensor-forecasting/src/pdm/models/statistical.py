"""Reusable statsmodels adapters for fixed-origin sensor forecasts."""
from dataclasses import dataclass
from pathlib import Path
import pickle

import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.api import VAR
from statsmodels.tsa.ar_model import AutoReg
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.statespace.varmax import VARMAX
from statsmodels.tsa.stattools import acf, adfuller

MULTIVARIATE = {"var", "varma", "varima", "varmax"}
EXOGENOUS = {"arimax", "sarimax", "varmax"}
BASELINES = {"ar", "ma", "arima", "sarima", "ses", "holt"}
STATISTICAL = MULTIVARIATE | EXOGENOUS | BASELINES | {"arma", "holt_winters"}


def difference(values: np.ndarray, order: int) -> tuple[np.ndarray, list[np.ndarray]]:
    """Difference along time and retain the last value at each integration level."""
    values = np.asarray(values, dtype=float)
    if not isinstance(order, int) or not 0 <= order < len(values):
        raise ValueError("Integration order must be non-negative and smaller than history")
    anchors = []
    for _ in range(order):
        anchors.append(values[-1].copy())
        values = np.diff(values, axis=0)
    return values, anchors


def integrate(forecast: np.ndarray, anchors: list[np.ndarray]) -> np.ndarray:
    """Invert repeated differencing across the complete forecast horizon."""
    for last in reversed(anchors):
        forecast = np.cumsum(forecast, axis=0) + last
    return forecast


def _order(values: list, length: int) -> tuple:
    if len(values) != length or any(type(item) is not int or item < 0 for item in values):
        raise ValueError(f"Order requires {length} non-negative integers")
    return tuple(values)


def _adf(values: np.ndarray, names: list[str]) -> dict:
    return {name: float(adfuller(column)[1]) if np.ptp(column) else None
            for name, column in zip(names, values.T)}


def _exog(values: pd.DataFrame | None, index: pd.Index, columns: list[str]) -> np.ndarray | None:
    if not columns and values is None:
        return None
    if (values is None or list(values.columns) != columns or not values.index.equals(index)
            or not np.isfinite(values.to_numpy(dtype=float)).all()):
        raise ValueError("Finite exogenous inputs must match the requested columns and cycles")
    return values.to_numpy(dtype=float)


@dataclass
class StatisticalFit:
    """Fitted forecasting model, transformation state, and training diagnostics."""

    kind: str
    result: object
    columns: list[str]
    exog_columns: list[str]
    last_cycle: int
    history: np.ndarray
    center: np.ndarray
    scale: np.ndarray
    anchors: list[np.ndarray]
    diagnostics: dict

    def predict(self, index: pd.Index, exog: pd.DataFrame | None = None) -> pd.DataFrame:
        """Forecast contiguous future cycles, requiring aligned exogenous regressors."""
        if not len(index) or list(index) != list(range(self.last_cycle + 1, self.last_cycle + 1 + len(index))):
            raise ValueError("Forecast cycles must immediately follow the fitted history")
        external = _exog(exog, index, self.exog_columns)
        if self.kind == "var":
            prediction = self.result.forecast(self.history, len(index))
        elif external is not None:
            prediction = self.result.forecast(steps=len(index), exog=external)
        else:
            prediction = self.result.forecast(steps=len(index))
        values = np.asarray(prediction).reshape(len(index), len(self.columns))
        values = integrate(values, self.anchors) * self.scale + self.center
        if not np.isfinite(values).all():
            raise RuntimeError("Model produced non-finite forecasts")
        return pd.DataFrame(values, index=index, columns=self.columns)

    def save(self, path: Path) -> None:
        """Save the fitted statsmodels object and its forecast state."""
        with path.open("xb") as stream:
            pickle.dump(self, stream)

    @staticmethod
    def load(path: Path) -> "StatisticalFit":
        """Load a trusted local fit saved with compatible dependencies."""
        with path.open("rb") as stream:
            return pickle.load(stream)


def fit_statistical(kind: str, history: pd.DataFrame, config: dict,
                    exog: pd.DataFrame | None = None) -> StatisticalFit:
    """Fit one model on one contiguous engine history."""
    if kind not in STATISTICAL:
        raise ValueError(f"Unknown statistical model: {kind}")
    columns = list(history.columns)
    multi = kind in MULTIVARIATE
    if (multi and len(columns) < 2) or (not multi and len(columns) != 1):
        raise ValueError("Select two or more distinct targets for multivariate models, one otherwise")
    if len(history) < 20 or not np.all(np.diff(history.index) == 1):
        raise ValueError("At least 20 consecutive history cycles are required")
    values = history.to_numpy(dtype=float)
    if not np.isfinite(values).all() or np.any(np.ptp(values, axis=0) == 0):
        raise ValueError("History targets must be finite and nonconstant")
    exog_columns = list(config.get("exog", []))
    if (kind in EXOGENOUS) != bool(exog_columns):
        raise ValueError("This model requires exogenous columns" if kind in EXOGENOUS
                         else "This model does not accept exogenous columns")
    external = _exog(exog, history.index, exog_columns)
    diagnostics = {"history_adf_p": _adf(values, columns)}
    center, scale = (values.mean(axis=0), values.std(axis=0)) if multi else (np.zeros(1), np.ones(1))
    integration = config.get("integration", 0)
    if kind == "varima" and integration < 1:
        raise ValueError("VARIMA requires positive integration order")
    if kind not in {"var", "varima"} and integration:
        raise ValueError("Manual integration is supported for VAR and VARIMA")
    transformed, anchors = difference((values - center) / scale, integration)
    if len(transformed) < 20:
        raise ValueError("At least 20 observations are required after differencing")
    if integration:
        diagnostics["differenced_adf_p"] = _adf(transformed, columns)
    target = transformed[:, 0]
    maxiter = config.get("maxiter", 200)
    if kind == "var":
        max_lags = config["max_lags"]
        if type(max_lags) is not int or max_lags < 1:
            raise ValueError("max_lags must be a positive integer")
        model = VAR(transformed)
        selected = model.select_order(maxlags=max_lags).selected_orders[config.get("ic", "aic")]
        result = model.fit(max(1, selected))
        diagnostics.update(selected_lag=int(selected), fitted_lag=int(result.k_ar))
        if not result.is_stable():
            raise RuntimeError("VAR fit is unstable")
    elif multi:
        order = _order(config["order"], 2)
        if kind == "varma" and min(order) < 1:
            raise ValueError("VARMA requires positive AR and MA orders")
        result = VARMAX(transformed, order=order, exog=external).fit(maxiter=maxiter, disp=False)
    elif kind in {"holt_winters", "ses", "holt"}:
        trend = {"ses": None, "holt": "add"}.get(kind, config.get("trend"))
        seasonal = config.get("seasonal") if kind == "holt_winters" else None
        period = config.get("seasonal_periods") if seasonal else None
        if trend not in {None, "add", "mul"} or seasonal not in {None, "add", "mul"}:
            raise ValueError("Trend and seasonality must be add, mul, or null")
        damped = config.get("damped_trend", False)
        if damped and trend is None:
            raise ValueError("Damping requires a trend")
        if "mul" in {trend, seasonal} and np.any(target <= 0):
            raise ValueError("Multiplicative Holt-Winters requires strictly positive history")
        if seasonal and (type(period) is not int or period < 2 or len(target) < 2 * period):
            raise ValueError("Seasonal Holt-Winters requires at least two complete periods")
        result = ExponentialSmoothing(target, trend=trend, seasonal=seasonal,
                                      seasonal_periods=period, damped_trend=damped).fit(optimized=True)
    elif kind == "ar":
        result = AutoReg(target, lags=1, trend="c").fit()
    elif kind in {"sarima", "sarimax"}:
        seasonal_order = _order(config["seasonal_order"], 4)
        period = seasonal_order[-1]
        if not any(seasonal_order[:3]) or period < 2 or len(target) < 2 * period + 1:
            raise ValueError("Seasonal ARIMA requires seasonal terms and at least two complete periods")
        result = SARIMAX(target, exog=external, order=_order(config["order"], 3),
                         seasonal_order=seasonal_order, enforce_stationarity=kind != "sarima",
                         enforce_invertibility=kind != "sarima").fit(maxiter=maxiter, disp=False)
    else:
        p, d, q = _order(config["order"], 3)
        if kind == "arma" and (d or not p or not q):
            raise ValueError("ARMA requires d=0 and positive p and q")
        result = ARIMA(target, exog=external, order=(p, d, q)).fit(
            method_kwargs={"maxiter": maxiter})
    optimizer = getattr(result, "mle_retvals", None)
    if optimizer and not optimizer.get("converged", optimizer.get("success", True)):
        raise RuntimeError(f"{kind} optimizer did not converge")
    if kind in {"sarima", "sarimax", "holt_winters"} and (kind != "holt_winters" or seasonal):
        changes = np.diff(target)
        seasonal_acf = float(acf(changes, nlags=period)[period])
        threshold = float(1.96 / np.sqrt(len(changes)))
        diagnostics.update(seasonal_period=period, differenced_seasonal_acf=seasonal_acf,
                           seasonal_acf_threshold=threshold,
                           seasonal_signal=abs(seasonal_acf) > threshold)
    residuals = np.asarray(result.resid).reshape(-1, len(columns))
    burn = max(getattr(result, "loglikelihood_burn", 0), 1)
    diagnostics["residual_ljung_box_p"] = {
        name: float(acorr_ljungbox(series[burn:], lags=[min(10, (len(series) - burn) // 5)],
                                  return_df=True)["lb_pvalue"].iloc[0])
        for name, series in zip(columns, residuals.T) if len(series) - burn >= 5
    }
    return StatisticalFit(kind, result, columns, exog_columns, int(history.index[-1]), transformed,
                          center, scale, anchors, diagnostics)
