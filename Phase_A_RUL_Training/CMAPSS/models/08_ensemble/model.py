"""Validation-fitted weighted averaging and positive Ridge stacking."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from sklearn.linear_model import Ridge


@dataclass(frozen=True)
class EnsembleFit:
    """Fitted parameters and validation predictions for both ensemble methods."""

    weighted_weights: np.ndarray
    ridge_coefficients: np.ndarray
    ridge_intercept: float
    weighted_validation: np.ndarray
    ridge_validation: np.ndarray


def _validate_predictions(predictions: np.ndarray, truth: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Validate a (rows, members) prediction matrix and aligned target vector."""
    matrix = np.asarray(predictions, dtype=np.float64)
    target = np.asarray(truth, dtype=np.float64).reshape(-1)
    if matrix.ndim != 2 or matrix.shape[0] != target.size or matrix.shape[1] < 1:
        raise ValueError("predictions must have shape (n_rows, n_members) aligned to truth")
    if target.size == 0 or not np.isfinite(matrix).all() or not np.isfinite(target).all():
        raise ValueError("predictions and truth must be non-empty and finite")
    return matrix, target


def fit_ensembles(
    predictions: np.ndarray, truth: np.ndarray, ridge_alpha: float = 1.0
) -> EnsembleFit:
    """Fit simplex-constrained weights and positive Ridge using validation only."""
    matrix, target = _validate_predictions(predictions, truth)
    if ridge_alpha < 0:
        raise ValueError("ridge_alpha must be non-negative")
    n_members = matrix.shape[1]
    initial = np.full(n_members, 1.0 / n_members)

    def objective(weights: np.ndarray) -> float:
        residual = matrix @ weights - target
        return float(np.mean(np.square(residual)))

    def gradient(weights: np.ndarray) -> np.ndarray:
        residual = matrix @ weights - target
        return 2.0 * matrix.T @ residual / target.size

    result = minimize(
        objective,
        initial,
        jac=gradient,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * n_members,
        constraints=({"type": "eq", "fun": lambda weights: weights.sum() - 1.0,
                      "jac": lambda weights: np.ones_like(weights)},),
        options={"maxiter": 2000, "ftol": 1e-12},
    )
    if not result.success:
        raise RuntimeError(f"Weighted-average optimization failed: {result.message}")
    weights = np.asarray(result.x, dtype=np.float64)
    if np.any(weights < -1e-8) or not np.isclose(weights.sum(), 1.0, atol=1e-7):
        raise RuntimeError("Weighted-average optimizer violated the simplex constraints")
    weights = np.clip(weights, 0.0, 1.0)
    weights /= weights.sum()

    ridge = Ridge(alpha=ridge_alpha, positive=True, fit_intercept=True)
    ridge.fit(matrix, target)
    coefficients = np.asarray(ridge.coef_, dtype=np.float64).reshape(-1)
    intercept = float(np.asarray(ridge.intercept_).reshape(-1)[0])
    return EnsembleFit(
        weighted_weights=weights,
        ridge_coefficients=coefficients,
        ridge_intercept=intercept,
        weighted_validation=matrix @ weights,
        ridge_validation=np.asarray(ridge.predict(matrix), dtype=np.float64).reshape(-1),
    )


def apply_weighted(predictions: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Combine member predictions with a validated non-negative simplex vector."""
    matrix = np.asarray(predictions, dtype=np.float64)
    vector = np.asarray(weights, dtype=np.float64).reshape(-1)
    if matrix.ndim != 2 or matrix.shape[1] != vector.size:
        raise ValueError("weights must match the member dimension of predictions")
    if np.any(vector < 0) or not np.isclose(vector.sum(), 1.0, atol=1e-7):
        raise ValueError("weights must be non-negative and sum to one")
    return matrix @ vector


def apply_ridge(predictions: np.ndarray, coefficients: np.ndarray, intercept: float) -> np.ndarray:
    """Apply saved positive Ridge coefficients to member predictions."""
    matrix = np.asarray(predictions, dtype=np.float64)
    vector = np.asarray(coefficients, dtype=np.float64).reshape(-1)
    if matrix.ndim != 2 or matrix.shape[1] != vector.size:
        raise ValueError("Ridge coefficients must match the member dimension")
    if np.any(vector < -1e-10):
        raise ValueError("Ridge coefficients must be non-negative")
    return matrix @ vector + float(intercept)
