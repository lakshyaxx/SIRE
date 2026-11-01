"""Build the fixed-seed CMAPSS report and validation-selected model registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from common.config import DATASET_IDS, cmapss_root
from common.metrics import compute_metrics
from common.registry import write_registry
from common.val_last import select_val_last, val_last_metrics

SEEDS = (42, 43, 44)
MODELS = (
    "01_lightgbm", "02_lstm", "03_bilstm_attention", "04_cnn1d",
    "05_transformer", "06_autoencoder", "07_cnn_transformer", "08_ensemble",
)
METRICS = ("rmse", "mae", "mse", "nasa_score", "r2")


def _mean_std(values: list[float]) -> tuple[float, float]:
    """Return mean and sample standard deviation over at least two seeds."""
    if not values:
        raise ValueError("Cannot aggregate an empty metric series")
    return float(np.mean(values)), float(np.std(values, ddof=1)) if len(values) > 1 else 0.0


def _fmt(values: list[float]) -> str:
    """Format a mean and sample standard deviation for the report."""
    mean, deviation = _mean_std(values)
    return f"{mean:.4f} ± {deviation:.4f}"


def _metric_row(frame: pd.DataFrame, dataset: str, model: str, seed: int, split: str, target: str | None = None) -> pd.Series:
    """Fetch exactly one comparison row for a model run."""
    mask = frame.dataset.eq(dataset) & frame.model.eq(model) & frame.seed.eq(seed) & frame.split.eq(split)
    if target is not None:
        mask &= frame.target_type.eq(target)
    rows = frame.loc[mask]
    if len(rows) != 1:
        raise ValueError(f"Expected one comparison row for {dataset}/{model}/seed{seed}/{split}/{target}, found {len(rows)}")
    return rows.iloc[0]


def _collect_val_last(root: Path, dataset: str, model: str, seed: int) -> dict[str, Any]:
    """Sample, score, and persist validation last/truncation metrics for one run."""
    output = root / "models" / model / "outputs" / dataset / f"seed_{seed}"
    predictions_path = output / "predictions_val.csv"
    if not predictions_path.is_file():
        raise FileNotFoundError(f"Missing validation predictions: {predictions_path}")
    selected = select_val_last(pd.read_csv(predictions_path), random_points=5, seed=42)
    scores = val_last_metrics(selected, compute_metrics)
    selected.to_csv(output / "predictions_val_last.csv", index=False)
    payload = {"dataset": dataset, "model": model, "seed": seed, "sampling_seed": 42,
               "random_truncations_per_engine": 5, "n": int(len(selected)), "metrics": scores}
    (output / "val_last_metrics.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _robustness(frame: pd.DataFrame, dataset: str, model: str, target: str) -> tuple[str, float, float]:
    """Classify RMSE against the paired baseline seed variation."""
    gaps: list[float] = []
    for seed in SEEDS:
        baseline = _metric_row(frame, dataset, "01_lightgbm", seed, "test", target)
        candidate = _metric_row(frame, dataset, model, seed, "test", target)
        gaps.append(float(baseline.rmse) - float(candidate.rmse))
    mean_gap, spread = _mean_std(gaps)
    if mean_gap > spread:
        verdict = "better than baseline"
    elif mean_gap < -spread:
        verdict = "worse than baseline"
    else:
        verdict = "within noise"
    return verdict, mean_gap, spread


def _write_report(root: Path, comparison: pd.DataFrame, scores: dict[tuple[str, str, int], dict[str, Any]]) -> None:
    """Write per-dataset model rankings and multi-seed metric summaries."""
    lines = [
        "# CMAPSS final results (seeds 42, 43, 44)", "",
        "Every mean is over the three listed seeds; ± is sample standard deviation (ddof=1).",
        "`val_last` uses the last validation endpoint and five fixed-seed random truncation endpoints per validation engine (sampling seed 42). It is the selection metric; official test metrics are descriptive only.",
        "A test RMSE gap is called better/worse than baseline only when the mean paired LightGBM-minus-model gap exceeds the sample standard deviation of those three paired gaps; all smaller gaps are within noise.",
        "",
    ]
    robust_rows: list[dict[str, Any]] = []
    for dataset in DATASET_IDS:
        lines.extend([f"## {dataset}", "", "### Validation ranking (val_last clipped RUL)", "",
                      "| Rank | Model | RMSE | MAE | MSE | NASA score | R² |", "|---:|---|---:|---:|---:|---:|---:|"])
        ranked = sorted(MODELS, key=lambda model: np.mean([
            scores[(dataset, model, seed)]["metrics"]["clipped"]["rmse"] for seed in SEEDS
        ]))
        for rank, model in enumerate(ranked, 1):
            values = {
                metric: [scores[(dataset, model, seed)]["metrics"]["clipped"][metric] for seed in SEEDS]
                for metric in METRICS
            }
            lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
                rank, model, *(_fmt(values[metric]) for metric in METRICS)
            ))
        for target, label in (("raw", "Raw official test RUL"), ("clipped", "Clipped test RUL")):
            lines.extend(["", f"### {label}", "", "| Model | RMSE | MAE | MSE | NASA score | R² | RMSE vs baseline |", "|---|---:|---:|---:|---:|---:|---|"])
            for model in MODELS:
                aggregate = {
                    metric: [float(_metric_row(comparison, dataset, model, seed, "test", target)[metric]) for seed in SEEDS]
                    for metric in METRICS
                }
                verdict, gap, spread = _robustness(comparison, dataset, model, target)
                robust_rows.append({"dataset": dataset, "model": model, "target": target, "verdict": verdict, "gap": gap, "spread": spread})
                delta = "baseline" if model == "01_lightgbm" else f"{verdict} (gap {gap:+.4f}, paired SD {spread:.4f})"
                lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
                    model, *(_fmt(aggregate[metric]) for metric in METRICS), delta
                ))
        lines.extend(["", "### Validation metrics (raw and clipped)", "",
                      "| Model | Target | RMSE | MAE | MSE | NASA score | R² |", "|---|---|---:|---:|---:|---:|---:|"])
        for model in MODELS:
            for target in ("raw", "clipped"):
                aggregate = {metric: [scores[(dataset, model, seed)]["metrics"][target][metric] for seed in SEEDS] for metric in METRICS}
                lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
                    model, target, *(_fmt(aggregate[metric]) for metric in METRICS)
                ))
        best_val = ranked[0]
        best_nasa = min(MODELS, key=lambda model: np.mean([
            scores[(dataset, model, seed)]["metrics"]["clipped"]["nasa_score"] for seed in SEEDS
        ]))
        lines.extend(["", f"Best by val_last RMSE: **{best_val}**. Best by val_last NASA score: **{best_nasa}**.", ""])

    lines.extend(["## Robustness summary", "", "RMSE robustness is assessed separately for raw and clipped test targets using paired seed gaps.", ""])
    for dataset in DATASET_IDS:
        raw_better = [row["model"] for row in robust_rows if row["dataset"] == dataset and row["target"] == "raw" and row["model"] != "01_lightgbm" and row["verdict"] == "better than baseline"]
        clipped_better = [row["model"] for row in robust_rows if row["dataset"] == dataset and row["target"] == "clipped" and row["model"] != "01_lightgbm" and row["verdict"] == "better than baseline"]
        raw_noise = [row["model"] for row in robust_rows if row["dataset"] == dataset and row["target"] == "raw" and row["model"] != "01_lightgbm" and row["verdict"] == "within noise"]
        clipped_noise = [row["model"] for row in robust_rows if row["dataset"] == dataset and row["target"] == "clipped" and row["model"] != "01_lightgbm" and row["verdict"] == "within noise"]
        raw_worse = [row["model"] for row in robust_rows if row["dataset"] == dataset and row["target"] == "raw" and row["model"] != "01_lightgbm" and row["verdict"] == "worse than baseline"]
        clipped_worse = [row["model"] for row in robust_rows if row["dataset"] == dataset and row["target"] == "clipped" and row["model"] != "01_lightgbm" and row["verdict"] == "worse than baseline"]
        lines.append(f"- **{dataset}:** robustly better — raw {', '.join(raw_better) or 'none'}, clipped {', '.join(clipped_better) or 'none'}; within noise — raw {', '.join(raw_noise) or 'none'}, clipped {', '.join(clipped_noise) or 'none'}; robustly worse — raw {', '.join(raw_worse) or 'none'}, clipped {', '.join(clipped_worse) or 'none'}.")
    hardest = max(DATASET_IDS, key=lambda dataset: min(np.mean([
        scores[(dataset, model, seed)]["metrics"]["clipped"]["rmse"] for seed in SEEDS
    ]) for model in MODELS))
    lines.extend(["", f"Hardest dataset by its best model's mean val_last RMSE: **{hardest}**.", ""])
    ablation = comparison.loc[comparison.model.eq("01_lightgbm_w50")]
    if not ablation.empty:
        lines.extend(["## LightGBM window-length ablation (w50)", "", "Only `window_length` differs from the 30-cycle baseline configuration; results use the same seeds. Δ is 50-cycle minus 30-cycle RMSE (negative favors 50). Validation uses the same `val_last` sampling rule as the model ranking.", "", "| Dataset | Split/target | 30-cycle RMSE | 50-cycle RMSE | Δ RMSE |", "|---|---|---:|---:|---:|"])
        for dataset in DATASET_IDS:
            base_val_last: list[float] = []
            wide_val_last: list[float] = []
            for seed in SEEDS:
                for model, target_list in (("01_lightgbm", base_val_last), ("01_lightgbm_w50", wide_val_last)):
                    pred_path = root / "models" / "01_lightgbm" / ("outputs" if model == "01_lightgbm" else "outputs_w50") / dataset / f"seed_{seed}" / "predictions_val.csv"
                    selected = select_val_last(pd.read_csv(pred_path), random_points=5, seed=42)
                    target_list.append(float(val_last_metrics(selected, compute_metrics)["clipped"]["rmse"]))
            entries = [("val_last clipped", base_val_last, wide_val_last)]
            for split, target, label in (("test", "raw", "test raw"), ("test", "clipped", "test clipped")):
                base = [float(_metric_row(comparison, dataset, "01_lightgbm", seed, split, target).rmse) for seed in SEEDS]
                wide = [float(_metric_row(comparison, dataset, "01_lightgbm_w50", seed, split, target).rmse) for seed in SEEDS]
                entries.append((label, base, wide))
            for label, base, wide in entries:
                gap = [wide_value - base_value for wide_value, base_value in zip(wide, base)]
                lines.append(f"| {dataset} | {label} | {_fmt(base)} | {_fmt(wide)} | {_fmt(gap)} |")
        lines.append("")

    lines.extend(["", "## Autoencoder onset diagnostics", "", "| Dataset | Mean onset detection rate | Pooled median lead (cycles) |", "|---|---:|---:|"])
    all_leads: list[float] = []
    total_detected = 0
    total_units = 0
    for dataset in DATASET_IDS:
        dataset_shares: list[float] = []
        dataset_leads: list[float] = []
        for seed in SEEDS:
            metrics_path = root / "models" / "06_autoencoder" / "outputs" / dataset / f"seed_{seed}" / "metrics.json"
            onset_path = metrics_path.parent / "onset.csv"
            if metrics_path.exists() and onset_path.exists():
                payload = json.loads(metrics_path.read_text(encoding="utf-8"))
                onset = pd.read_csv(onset_path)
                lead_column = next((name for name in ("lead_time_cycles", "lead_time", "median_lead_time_cycles") if name in onset.columns), None)
                if lead_column:
                    detected = onset.loc[onset[lead_column].notna(), lead_column].astype(float).tolist()
                    dataset_leads.extend(detected)
                    dataset_shares.append(float(payload["health_metrics"]["test_onset"]["onset_share"]))
                    total_detected += len(detected)
                    total_units += len(onset)
        all_leads.extend(dataset_leads)
        rate_text = f"{float(np.mean(dataset_shares)):.1%}" if dataset_shares else "n/a"
        median_text = f"{float(np.median(dataset_leads)):.2f}" if dataset_leads else "n/a"
        lines.append(f"| {dataset} | {rate_text} | {median_text} |")
    if all_leads:
        pooled_rate = total_detected / total_units if total_units else 0.0
        lines.extend(["", f"Across all subsets and seeds: {total_detected}/{total_units} engine-runs detected ({pooled_rate:.1%}); pooled median lead time {float(np.median(all_leads)):.2f} cycles.", ""])
    (root / "results" / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def finalize() -> Path:
    """Validate all requested runs, write val_last files, report, and registry."""
    root = cmapss_root()
    comparison = pd.read_csv(root / "results" / "comparison.csv")
    result_index: dict[tuple[str, str, int], dict[str, Any]] = {}
    registry: dict[str, Any] = {
        "track": "CMAPSS", "seeds": list(SEEDS), "selection_metric": "val_last.clipped.rmse",
        "val_last_protocol": {"random_truncations_per_engine": 5, "sampling_seed": 42},
        "datasets": {},
    }
    for dataset in DATASET_IDS:
        model_entries: dict[str, Any] = {}
        model_val: dict[str, list[dict[str, Any]]] = {}
        for model in MODELS:
            per_seed: list[dict[str, Any]] = []
            for seed in SEEDS:
                for split, target in (("val", "clipped"), ("test", "raw"), ("test", "clipped")):
                    _metric_row(comparison, dataset, model, seed, split, target)
                result = _collect_val_last(root, dataset, model, seed)
                result_index[(dataset, model, seed)] = result
                per_seed.append(result)
            model_val[model] = per_seed
            best_seed = min(SEEDS, key=lambda seed: result_index[(dataset, model, seed)]["metrics"]["clipped"]["rmse"])
            val_aggregate = {
                target: {metric: {"mean": _mean_std([result_index[(dataset, model, seed)]["metrics"][target][metric] for seed in SEEDS])[0],
                                  "std": _mean_std([result_index[(dataset, model, seed)]["metrics"][target][metric] for seed in SEEDS])[1]}
                         for metric in METRICS}
                for target in ("raw", "clipped")
            }
            best_val_metrics = result_index[(dataset, model, best_seed)]["metrics"]
            test_selected = {
                target: {metric: float(_metric_row(comparison, dataset, model, best_seed, "test", target)[metric]) for metric in METRICS}
                for target in ("raw", "clipped")
            }
            test_mean_std = {
                target: {metric: {"mean": _mean_std([float(_metric_row(comparison, dataset, model, seed, "test", target)[metric]) for seed in SEEDS])[0],
                                  "std": _mean_std([float(_metric_row(comparison, dataset, model, seed, "test", target)[metric]) for seed in SEEDS])[1]}
                         for metric in METRICS}
                for target in ("raw", "clipped")
            }
            val_all = [float(_metric_row(comparison, dataset, model, seed, "val").rmse) for seed in SEEDS]
            model_entries[model] = {
                "predict_module": f"models/{model}/predict.py",
                "artifact_dir": f"models/{model}/outputs/{dataset}/seed_{best_seed}",
                "seed": best_seed,
                "val_rmse": float(best_val_metrics["clipped"]["rmse"]),
                "val_rmse_mean_std": {"mean": _mean_std(val_all)[0], "std": _mean_std(val_all)[1]},
                "val_last_mean_std": val_aggregate,
                "test_metrics": test_selected,
                "test_metrics_mean_std": test_mean_std,
                "seed_by_val_last_nasa": min(SEEDS, key=lambda seed: result_index[(dataset, model, seed)]["metrics"]["clipped"]["nasa_score"]),
            }
        best_val_model = min(MODELS, key=lambda model: np.mean([result_index[(dataset, model, seed)]["metrics"]["clipped"]["rmse"] for seed in SEEDS]))
        best_nasa_model = min(MODELS, key=lambda model: np.mean([result_index[(dataset, model, seed)]["metrics"]["clipped"]["nasa_score"] for seed in SEEDS]))
        registry["datasets"][dataset] = {
            "models": model_entries,
            "best_by_val_rmse": best_val_model,
            "best_by_nasa_score": best_nasa_model,
            "best_seed_by_val_rmse": model_entries[best_val_model]["seed"],
            "best_seed_by_nasa_score": model_entries[best_nasa_model]["seed_by_val_last_nasa"],
            "health_indicator_model": "06_autoencoder",
        }
    _write_report(root, comparison, result_index)
    return write_registry(registry)


if __name__ == "__main__":
    print(finalize())
