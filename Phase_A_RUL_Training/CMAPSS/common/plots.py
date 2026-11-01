"""Common evaluation figures for training histories and RUL predictions."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_loss_curve(history: pd.DataFrame, path: str | Path) -> Path:
    """Plot training loss and validation RMSE history."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(8, 5))
    axis.plot(history["epoch"], history["train_loss"], label="train loss")
    if "val_rmse" in history:
        secondary = axis.twinx()
        secondary.plot(history["epoch"], history["val_rmse"], color="tab:orange", label="validation RMSE")
        secondary.set_ylabel("Validation RMSE (cycles)")
    axis.set(xlabel="Epoch", ylabel="Training loss", title="Training history")
    axis.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(target, dpi=150)
    plt.close(fig)
    return target


def plot_metric_history(
    history: pd.DataFrame,
    x_column: str,
    train_column: str,
    validation_column: str,
    path: str | Path,
    metric_name: str,
) -> Path:
    """Plot a train/validation metric history such as LightGBM RMSE by round."""
    required = {x_column, train_column, validation_column}
    missing = required - set(history.columns)
    if missing:
        raise ValueError(f"Metric history is missing columns: {sorted(missing)}")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(8, 5))
    axis.plot(history[x_column], history[train_column], label=f"train {metric_name}")
    axis.plot(history[x_column], history[validation_column], label=f"validation {metric_name}")
    axis.set(xlabel=x_column.replace("_", " ").title(), ylabel=metric_name, title=f"{metric_name} by training iteration")
    axis.legend()
    axis.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(target, dpi=150)
    plt.close(fig)
    return target


def plot_prediction_diagnostics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    path_dir: str | Path,
    units: np.ndarray | None = None,
) -> list[Path]:
    """Write predicted-vs-true, residual, RUL-band, and worst-10 plots."""
    truth = np.asarray(y_true, dtype=float).reshape(-1)
    pred = np.asarray(y_pred, dtype=float).reshape(-1)
    if truth.size == 0 or truth.shape != pred.shape:
        raise ValueError("truth and predictions must have the same non-empty shape")
    output = Path(path_dir)
    output.mkdir(parents=True, exist_ok=True)
    residual = pred - truth
    generated: list[Path] = []

    fig, axis = plt.subplots(figsize=(6, 6))
    axis.scatter(truth, pred, s=10, alpha=0.5)
    lower, upper = min(truth.min(), pred.min()), max(truth.max(), pred.max())
    axis.plot([lower, upper], [lower, upper], "k--", linewidth=1)
    axis.set(xlabel="True RUL (cycles)", ylabel="Predicted RUL (cycles)", title="Predicted vs true RUL")
    axis.grid(alpha=0.25)
    fig.tight_layout()
    target = output / "predicted_vs_true.png"
    fig.savefig(target, dpi=150)
    plt.close(fig)
    generated.append(target)

    fig, axis = plt.subplots(figsize=(7, 5))
    axis.hist(residual, bins=30, color="tab:blue", alpha=0.8)
    axis.axvline(0, color="black", linestyle="--")
    axis.set(xlabel="Prediction error (cycles)", ylabel="Count", title="Residual histogram")
    fig.tight_layout()
    target = output / "residual_histogram.png"
    fig.savefig(target, dpi=150)
    plt.close(fig)
    generated.append(target)

    edges = np.array([0, 20, 40, 60, 80, 100, 125, np.inf], dtype=float)
    band = pd.cut(truth, edges, right=False, include_lowest=True)
    grouped = pd.DataFrame({"band": band, "abs_error": np.abs(residual)}).groupby("band", observed=False)["abs_error"].mean()
    fig, axis = plt.subplots(figsize=(9, 5))
    grouped.plot.bar(ax=axis)
    axis.set(xlabel="True RUL band (cycles)", ylabel="Mean absolute error", title="Error by RUL band")
    axis.tick_params(axis="x", labelrotation=30)
    fig.tight_layout()
    target = output / "error_by_rul_band.png"
    fig.savefig(target, dpi=150)
    plt.close(fig)
    generated.append(target)

    sample_ids = np.asarray(units).reshape(-1) if units is not None else np.arange(truth.size)
    if sample_ids.size != truth.size:
        raise ValueError("units length must match prediction count")
    worst = np.argsort(np.abs(residual))[-10:][::-1]
    fig, axis = plt.subplots(figsize=(9, 5))
    labels = [str(sample_ids[index]) for index in worst]
    axis.bar(labels, residual[worst])
    axis.axhline(0, color="black", linewidth=0.8)
    axis.set(xlabel="Engine id", ylabel="Prediction error (cycles)", title="Worst 10 predictions")
    fig.tight_layout()
    target = output / "worst_10_engines.png"
    fig.savefig(target, dpi=150)
    plt.close(fig)
    generated.append(target)
    return generated
