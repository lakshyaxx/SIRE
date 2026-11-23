"""Create versioned, aligned sensor benchmark reports and diagnostic figures."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.graphics.tsaplots import plot_acf

from pdm.evaluation.sensor_metrics import METRICS


def model_figures(directory: Path, model: str, history: pd.DataFrame, actual: pd.DataFrame,
                  forecast: pd.DataFrame) -> None:
    """Save forecast, predicted versus actual, and residual diagnostics per target."""
    for target in actual:
        name = f"{model}_{target}.png"
        y, pred = actual[target], forecast[target]
        residual = y - pred
        fig, ax = plt.subplots(figsize=(9, 4))
        history[target].tail(2 * len(y)).plot(ax=ax, label="Observed history")
        ax.plot(y.index, y, label="Held-out actual")
        ax.plot(pred.index, pred, label="Forecast")
        ax.set(xlabel="Cycle", ylabel=target, title=model)
        ax.legend()
        fig.savefig(directory / "figures/forecasts" / name, bbox_inches="tight")
        plt.close(fig)

        fig, (scatter, errors, correlation) = plt.subplots(1, 3, figsize=(13, 4))
        scatter.scatter(y, pred, s=12)
        limits = [min(y.min(), pred.min()), max(y.max(), pred.max())]
        scatter.plot(limits, limits, linestyle="--")
        scatter.set(xlabel="Actual", ylabel="Predicted")
        errors.plot(y.index, residual)
        errors.axhline(0, linestyle="--")
        errors.set(xlabel="Cycle", ylabel="Actual minus predicted")
        if len(residual) >= 4 and np.ptp(residual):
            plot_acf(residual, lags=min(12, len(residual) // 2 - 1), ax=correlation)
        else:
            correlation.text(0.05, 0.5, "Insufficient variation for ACF")
        fig.savefig(directory / "figures/diagnostics" / name, bbox_inches="tight")
        plt.close(fig)


def comparison_report(directory: Path, rows: list[dict], attempts: list[dict]) -> None:
    """Write per-target metrics, exact-target macro scores, charts and winners."""
    reports = directory / "metrics"
    columns = ["model", "protocol", "target", *METRICS, "training_seconds", "inference_seconds"]
    scores = pd.DataFrame(rows, columns=columns)
    for metric in METRICS:
        scores[metric] = pd.to_numeric(scores[metric])
    scores.to_csv(reports / "model_comparison.csv", index=False)
    pd.DataFrame(attempts, columns=["model", "status", "detail"]).to_csv(reports / "attempts.csv", index=False)
    aggregates = []
    for (model, protocol), group in scores.groupby(["model", "protocol"]):
        if len(group) > 1:
            aggregates.append({"model": model, "protocol": protocol,
                               "targets": "+".join(group["target"]),
                               **{f"macro_{name}": group[name].mean(skipna=False) for name in METRICS}})
    pd.DataFrame(aggregates, columns=["model", "protocol", "targets", *[f"macro_{m}" for m in METRICS]]
                 ).to_csv(reports / "multivariate_macro.csv", index=False)
    lines = ["# Fixed-origin sensor benchmark", "", "CPU smoke scores are excluded from winners.", ""]
    eligible = scores.loc[scores["protocol"] != "cpu_smoke"]
    for target, group in eligible.groupby("target"):
        winner = group.loc[group["rmse"].idxmin()]
        lines.append(f"- {target}: {winner['model']} had the lowest RMSE ({winner['rmse']:.6g}).")
        for metric in ["mae", "rmse", "r2", "training_seconds"]:
            series = pd.to_numeric(group.set_index("model")[metric], errors="coerce").dropna()
            if series.empty:
                continue
            fig, ax = plt.subplots(figsize=(8, max(3, len(series) * 0.33)))
            series.sort_values(ascending=metric == "r2").plot.barh(ax=ax)
            ax.set(xlabel=metric, ylabel="", title=target)
            fig.savefig(directory / "figures/comparisons" / f"{target}_{metric}.png", bbox_inches="tight")
            plt.close(fig)
    if eligible.empty:
        lines.append("No eligible benchmark models completed.")
    (directory / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
