"""Calibrate ensemble spread on val_last and compare interval predictors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from common.config import DATASET_IDS, cmapss_root
from common.registry import read_registry, write_registry
from common.uncertainty import calibrate_spread_scale, interval_metrics, spread_interval
from common.val_last import select_val_last

SEEDS = (42, 43, 44)
MEMBERS = (
    "01_lightgbm", "02_lstm", "03_bilstm_attention", "04_cnn1d",
    "05_transformer", "06_autoencoder", "07_cnn_transformer",
)
METHODS = ("08_ensemble_member_spread", "01_lightgbm_quantile")


def _paths(dataset: str, seed: int, model: str, split: str) -> Path:
    """Resolve a model prediction path for a saved dataset/seed/split."""
    suffix = "val_last" if split == "val_last" else split
    return cmapss_root() / "models" / model / "outputs" / dataset / f"seed_{seed}" / f"predictions_{suffix}.csv"


def _member_spread(dataset: str, seed: int, split: str) -> tuple[pd.DataFrame, np.ndarray]:
    """Return ensemble point predictions and aligned per-member prediction spread."""
    reference = pd.read_csv(_paths(dataset, seed, "08_ensemble", split))
    member_frames: list[pd.DataFrame] = []
    source_split = "val" if split == "val_last" else "test"
    for model in MEMBERS:
        frame = pd.read_csv(_paths(dataset, seed, model, source_split))
        aligned = reference[["unit", "step"]].merge(
            frame[["unit", "step", "y_pred"]], on=["unit", "step"], how="left", validate="one_to_one"
        )
        if aligned.y_pred.isna().any():
            raise ValueError(f"Missing aligned {model} predictions for {dataset}/seed{seed}/{split}")
        member_frames.append(aligned.y_pred.to_numpy(dtype=float))
    matrix = np.column_stack(member_frames)
    return reference, np.std(matrix, axis=1, ddof=0)


def calibrate_ensemble() -> dict[str, dict[str, float]]:
    """Fit one validation-only member-spread scale per subset, pooled over seeds."""
    root = cmapss_root()
    result: dict[str, dict[str, float]] = {}
    for dataset in DATASET_IDS:
        truth: list[float] = []
        prediction: list[float] = []
        spread: list[float] = []
        for seed in SEEDS:
            frame, sigma = _member_spread(dataset, seed, "val_last")
            truth.extend(frame.y_true_raw.to_numpy(dtype=float))
            prediction.extend(frame.y_pred.to_numpy(dtype=float))
            spread.extend(sigma.tolist())
        factor = calibrate_spread_scale(truth, prediction, spread, target_coverage=0.8, z_value=1.28)
        low, high = spread_interval(prediction, spread, factor, z_value=1.28)
        validation_coverage = float(np.mean((np.asarray(truth) >= low) & (np.asarray(truth) <= high)))
        payload = {
            "dataset": dataset,
            "calibration_seed_policy": "pooled fixed seeds 42, 43, 44",
            "calibration_split": "val_last raw RUL",
            "target_coverage": 0.8,
            "z_value": 1.28,
            "spread_scale": factor,
            "pooled_val_last_coverage": validation_coverage,
            "n_validation_points": len(truth),
        }
        artifact = root / "results" / "artifacts" / dataset / "ensemble_uncertainty.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result[dataset] = payload
    return result


def _interval_row(
    method: str, dataset: str, seed: int, split: str, target: str,
    frame: pd.DataFrame, lower: np.ndarray, upper: np.ndarray,
) -> dict[str, Any]:
    """Score one prediction interval against one target flavor."""
    truth = frame[f"y_true_{target}"].to_numpy(dtype=float)
    prediction = frame.y_pred.to_numpy(dtype=float)
    return {
        "method": method,
        "dataset": dataset,
        "seed": seed,
        "split": split,
        "target": target,
        **interval_metrics(truth, lower, upper, prediction),
    }


def evaluate() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, float]]]:
    """Calibrate and evaluate both interval methods on val_last and test."""
    calibration = calibrate_ensemble()
    rows: list[dict[str, Any]] = []
    for dataset in DATASET_IDS:
        factor = calibration[dataset]["spread_scale"]
        for seed in SEEDS:
            for split in ("val_last", "test"):
                ensemble, sigma = _member_spread(dataset, seed, split)
                low, high = spread_interval(ensemble.y_pred, sigma, factor, z_value=1.28)
                for target in ("raw", "clipped"):
                    rows.append(_interval_row(
                        "08_ensemble_member_spread", dataset, seed, split, target, ensemble, low, high
                    ))
            qroot = cmapss_root() / "models" / "01_lightgbm_quantile" / "outputs" / dataset / f"seed_{seed}"
            for split in ("val", "test"):
                quantile = pd.read_csv(qroot / f"predictions_{split}.csv")
                if split == "val":
                    quantile = select_val_last(quantile, random_points=5, seed=42)
                    split_name = "val_last"
                else:
                    split_name = "test"
                low = quantile.y_lower.to_numpy(dtype=float)
                high = quantile.y_upper.to_numpy(dtype=float)
                for target in ("raw", "clipped"):
                    rows.append(_interval_row(
                        "01_lightgbm_quantile", dataset, seed, split_name, target, quantile, low, high
                    ))
    per_seed = pd.DataFrame(rows)
    summary_rows: list[dict[str, Any]] = []
    group_columns = ["method", "dataset", "split", "target"]
    for keys, group in per_seed.groupby(group_columns, sort=True):
        row = dict(zip(group_columns, keys))
        for metric in ("coverage", "mean_width", "width_abs_error_correlation"):
            values = group[metric].dropna().to_numpy(dtype=float)
            row[f"{metric}_mean"] = float(np.mean(values)) if values.size else float("nan")
            row[f"{metric}_std"] = float(np.std(values, ddof=1)) if values.size > 1 else 0.0
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    output_dir = cmapss_root() / "results"
    per_seed.to_csv(output_dir / "uncertainty_metrics_by_seed.csv", index=False)
    summary.to_csv(output_dir / "uncertainty_metrics.csv", index=False)
    _update_report(summary, calibration)
    _update_registry(calibration)
    return per_seed, summary, calibration


def _fmt(mean: float, std: float) -> str:
    """Format a seed aggregate as mean +/- sample standard deviation."""
    return f"{mean:.3f} +/- {std:.3f}"


def _update_report(summary: pd.DataFrame, calibration: dict[str, dict[str, float]]) -> None:
    """Append reproducible interval metrics and validation calibration to report."""
    report_path = cmapss_root() / "results" / "REPORT.md"
    original = report_path.read_text(encoding="utf-8")
    marker = "\n## Prediction uncertainty\n"
    if marker in original:
        original = original.split(marker, 1)[0]
    lines = [
        "", "## Prediction uncertainty", "",
        "Both interval predictors return `interval_80` and `uncertainty_method`; only these predictors expose uncertainty.",
        "The ensemble uses population standard deviation across its seven member RUL outputs. Its single multiplicative scale is calibrated separately per dataset on pooled seed 42/43/44 `val_last` raw-RUL residual ratios at the 80th percentile. No test labels enter calibration. The quantile LightGBM interval uses alpha 0.1/0.9 models trained with the existing LightGBM feature schema and validation-only quantile-loss early stopping.",
        "Width-error correlation is Pearson correlation between interval width and absolute point-prediction error. Values below 80% on test indicate under-coverage; values above 80% indicate over-coverage.",
        "", "### Ensemble validation calibration", "",
        "| Dataset | Spread scale | Pooled val_last raw coverage | Validation points |", "|---|---:|---:|---:|",
    ]
    for dataset in DATASET_IDS:
        item = calibration[dataset]
        lines.append(f"| {dataset} | {item['spread_scale']:.4f} | {item['pooled_val_last_coverage']:.1%} | {item['n_validation_points']} |")
    lines.extend(["", "### Interval quality by dataset", "", "Each cell is mean +/- sample SD across seeds 42, 43, 44.", ""])
    for dataset in DATASET_IDS:
        lines.extend([
            f"#### {dataset}", "",
            "| Method | Split/target | Coverage | Mean width (cycles) | Pearson width/absolute-error r |",
            "|---|---|---:|---:|---:|",
        ])
        part = summary.loc[summary.dataset.eq(dataset)]
        for _, row in part.sort_values(["method", "split", "target"]).iterrows():
            corr = _fmt(row.width_abs_error_correlation_mean, row.width_abs_error_correlation_std)
            lines.append(
                f"| {row.method} | {row.split} {row.target} | "
                f"{_fmt(row.coverage_mean, row.coverage_std)} | "
                f"{_fmt(row.mean_width_mean, row.mean_width_std)} | {corr} |"
            )
        lines.append("")
    lines.extend(["### Test coverage note", ""])
    for dataset in DATASET_IDS:
        notes: list[str] = []
        part = summary.loc[
            summary.dataset.eq(dataset) & summary.split.eq("test") & summary.target.eq("raw")
        ]
        for _, row in part.iterrows():
            coverage = float(row.coverage_mean)
            status = "near 80%" if 0.75 <= coverage <= 0.85 else "far from 80%"
            notes.append(f"{row.method}: {coverage:.1%} ({status})")
        lines.append(f"- **{dataset}:** " + "; ".join(notes) + ".")
    report_path.write_text(original.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")


def _update_registry(calibration: dict[str, dict[str, float]]) -> None:
    """Add uncertainty predictor references while preserving existing registry keys."""
    registry = read_registry()
    for dataset in DATASET_IDS:
        selected_seed = int(registry["datasets"][dataset]["models"]["01_lightgbm"]["seed"])
        registry["datasets"][dataset]["uncertainty"] = {
            "08_ensemble_member_spread": {
                "predict_module": "models/08_ensemble/predict.py",
                "calibration_artifact": f"results/artifacts/{dataset}/ensemble_uncertainty.json",
                "calibration_scale": float(calibration[dataset]["spread_scale"]),
                "calibration_split": "val_last raw RUL; pooled seeds 42, 43, 44",
            },
            "01_lightgbm_quantile": {
                "predict_module": "models/01_lightgbm_quantile/predict.py",
                "artifact_dir": f"models/01_lightgbm_quantile/outputs/{dataset}",
                "seed": selected_seed,
                "quantiles": [0.1, 0.9],
            },
        }
    write_registry(registry)


def main() -> None:
    """Evaluate intervals, report actual metrics, and update registry references."""
    _, summary, calibration = evaluate()
    print("Ensemble calibration:")
    for dataset, item in calibration.items():
        print(f"{dataset}: scale={item['spread_scale']:.6f}, val_last raw coverage={item['pooled_val_last_coverage']:.3f}")
    print(f"Wrote {len(summary)} dataset/method/split/target interval summaries.")


if __name__ == "__main__":
    main()
