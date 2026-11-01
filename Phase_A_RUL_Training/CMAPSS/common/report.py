"""Machine-readable comparison rows and generated CMAPSS summary reports."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .config import cmapss_root

COMPARISON_COLUMNS = (
    "track",
    "dataset",
    "model",
    "seed",
    "split",
    "level",
    "target_type",
    "n",
    "rmse",
    "mae",
    "mse",
    "r2",
    "nasa_score",
    "nasa_score_mean",
    "n_params",
    "train_seconds",
    "device",
    "config_hash",
    "timestamp",
)
ROW_KEY = ("track", "dataset", "model", "seed", "split", "level", "target_type")


def default_comparison_path() -> Path:
    """Return the canonical CMAPSS comparison CSV path."""
    return cmapss_root() / "results" / "comparison.csv"


def _normalize_rows(rows: Iterable[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    """Validate and order result records to the shared CSV schema."""
    frame = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
    if frame.empty:
        return pd.DataFrame(columns=COMPARISON_COLUMNS)
    missing = set(COMPARISON_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Comparison rows are missing columns: {sorted(missing)}")
    frame = frame.loc[:, COMPARISON_COLUMNS].copy()
    if frame[list(ROW_KEY)].isna().any().any():
        raise ValueError("comparison row keys cannot be empty")
    if frame["timestamp"].isna().any():
        frame.loc[frame["timestamp"].isna(), "timestamp"] = datetime.now(timezone.utc).isoformat()
    return frame


def replace_comparison_rows(
    rows: Iterable[Mapping[str, Any]] | pd.DataFrame,
    path: str | Path | None = None,
) -> pd.DataFrame:
    """Append or replace result rows by their canonical identity key."""
    target = Path(path) if path is not None else default_comparison_path()
    incoming = _normalize_rows(rows)
    if target.exists():
        current = pd.read_csv(target)
        if not current.empty:
            missing = set(COMPARISON_COLUMNS) - set(current.columns)
            if missing:
                raise ValueError(f"Existing comparison file is missing columns: {sorted(missing)}")
            current = current.loc[:, COMPARISON_COLUMNS]
        else:
            current = pd.DataFrame(columns=COMPARISON_COLUMNS)
    else:
        current = pd.DataFrame(columns=COMPARISON_COLUMNS)
    if not incoming.empty:
        incoming_keys = incoming[list(ROW_KEY)].drop_duplicates()
        marker = incoming_keys.astype(str).agg("\x1f".join, axis=1)
        current_marker = current[list(ROW_KEY)].astype(str).agg("\x1f".join, axis=1) if not current.empty else pd.Series(dtype=str)
        current = current.loc[~current_marker.isin(set(marker))]
        combined = incoming.reset_index(drop=True) if current.empty else pd.concat([current, incoming], ignore_index=True)
    else:
        combined = current
    combined = combined.drop_duplicates(subset=list(ROW_KEY), keep="last")
    if not combined.empty:
        combined = combined.sort_values(list(ROW_KEY), kind="stable").reset_index(drop=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    combined.to_csv(temporary, index=False)
    temporary.replace(target)
    return combined


def generate_report(
    comparison_path: str | Path | None = None,
    report_path: str | Path | None = None,
    figures_dir: str | Path | None = None,
) -> Path:
    """Regenerate REPORT.md and a test-RMSE chart from comparison rows."""
    results_dir = cmapss_root() / "results"
    csv_path = Path(comparison_path) if comparison_path is not None else results_dir / "comparison.csv"
    md_path = Path(report_path) if report_path is not None else results_dir / "REPORT.md"
    chart_dir = Path(figures_dir) if figures_dir is not None else results_dir / "figures"
    chart_dir.mkdir(parents=True, exist_ok=True)
    if csv_path.exists():
        frame = pd.read_csv(csv_path)
    else:
        frame = pd.DataFrame(columns=COMPARISON_COLUMNS)
    lines = ["# CMAPSS model report", "", "Generated from `comparison.csv`; metrics are produced by the training/evaluation code.", ""]
    if frame.empty:
        lines.extend(["No model results are recorded yet. The audit is complete; model comparisons will appear after training.", ""])
    else:
        required = set(COMPARISON_COLUMNS)
        if required - set(frame.columns):
            raise ValueError(f"Comparison file is missing columns: {sorted(required - set(frame.columns))}")
        for (dataset, seed, split, level, target_type), group in frame.groupby(
            ["dataset", "seed", "split", "level", "target_type"], dropna=False
        ):
            ranked = group.sort_values("rmse")
            lines.extend(
                [
                    f"## {dataset} — seed {seed}, {split}, level {level}, target {target_type}",
                    "",
                    "| Rank | Model | RMSE | MAE | MSE | NASA score | R² | Δ vs LightGBM RMSE | Δ vs best RMSE |",
                    "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
                ]
            )
            baseline_rows = group.loc[group["model"].eq("01_lightgbm"), "rmse"]
            baseline = float(baseline_rows.iloc[0]) if not baseline_rows.empty else None
            best = float(ranked["rmse"].iloc[0])
            for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
                baseline_delta = "—" if baseline is None or baseline == 0 else f"{(float(row['rmse']) / baseline - 1) * 100:+.2f}%"
                best_delta = "—" if best == 0 else f"{(float(row['rmse']) / best - 1) * 100:+.2f}%"
                lines.append(
                    f"| {rank} | {row['model']} | {row['rmse']:.4f} | {row['mae']:.4f} | {row['mse']:.4f} | {row['nasa_score']:.4f} | {row['r2']:.4f} | {baseline_delta} | {best_delta} |"
                )
            lines.append("")
        test_rows = frame.loc[frame["split"].eq("test") & frame["target_type"].eq("raw")]
        if not test_rows.empty:
            summary = test_rows.groupby(["dataset", "model"], as_index=False)["rmse"].mean()
            pivot = summary.pivot(index="dataset", columns="model", values="rmse")
            axis = pivot.plot(kind="bar", figsize=(10, 5))
            axis.set(ylabel="Test raw RMSE (cycles)", title="CMAPSS model comparison")
            axis.grid(axis="y", alpha=0.25)
            axis.legend(title="Model", bbox_to_anchor=(1.02, 1), loc="upper left")
            fig = axis.get_figure()
            fig.tight_layout()
            fig.savefig(chart_dir / "test_rmse_comparison.png", dpi=150)
            plt.close(fig)
            lines.extend(["## Test RMSE figure", "", "![Test raw RMSE by dataset and model](figures/test_rmse_comparison.png)", ""])
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def record_results(rows: Iterable[Mapping[str, Any]] | pd.DataFrame, path: str | Path | None = None) -> Path:
    """Replace matching CSV result rows and regenerate the report."""
    comparison_path = Path(path) if path is not None else default_comparison_path()
    replace_comparison_rows(rows, comparison_path)
    return generate_report(comparison_path)
