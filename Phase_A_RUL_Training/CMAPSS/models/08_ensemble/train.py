"""Fit and compare validation-weighted and stacked CMAPSS ensembles."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODEL_DIR = Path(__file__).resolve().parent
TRACK_ROOT = MODEL_DIR.parents[1]
if str(TRACK_ROOT) not in sys.path:
    sys.path.insert(0, str(TRACK_ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(TRACK_ROOT.parents[0] / ".venv" / "mplconfig"))

import numpy as np
import pandas as pd
import yaml

from common.config import DATASET_IDS, get_dataset_spec
from common.evaluate import evaluate_predictions
from common.plots import plot_prediction_diagnostics
from common.report import record_results
from common.train_utils import seed_everything

_MODEL_SPEC = importlib.util.spec_from_file_location(
    "sire_cmapss_08_ensemble_model", MODEL_DIR / "model.py"
)
if _MODEL_SPEC is None or _MODEL_SPEC.loader is None:
    raise ImportError("Cannot load ensemble model functions")
_MODEL_MODULE = importlib.util.module_from_spec(_MODEL_SPEC)
sys.modules[_MODEL_SPEC.name] = _MODEL_MODULE
_MODEL_SPEC.loader.exec_module(_MODEL_MODULE)
fit_ensembles = _MODEL_MODULE.fit_ensembles
apply_weighted = _MODEL_MODULE.apply_weighted
apply_ridge = _MODEL_MODULE.apply_ridge

MEMBER_MODELS = (
    "01_lightgbm", "02_lstm", "03_bilstm_attention", "04_cnn1d",
    "05_transformer", "06_autoencoder", "07_cnn_transformer",
)
LOG = logging.getLogger("ensemble_train")


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Read the ensemble YAML configuration."""
    config_path = Path(path) if path is not None else MODEL_DIR / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"Configuration at {config_path} must be a YAML mapping")
    return config


def _stable_hash(config: dict[str, Any]) -> str:
    """Hash effective config and fitted ensemble parameters deterministically."""
    value = json.dumps(config, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(value).hexdigest()


def _read_member_predictions(
    dataset: str, seed: int, split: str
) -> tuple[list[str], list[str], pd.DataFrame, np.ndarray]:
    """Load all required member predictions and verify row/label alignment."""
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for model_name in MEMBER_MODELS:
        path = (
            TRACK_ROOT / "models" / model_name / "outputs" / dataset
            / f"seed_{seed}" / f"predictions_{split}.csv"
        )
        if path.is_file():
            frames[model_name] = pd.read_csv(path)
        else:
            missing.append(model_name)
    if missing:
        raise FileNotFoundError(
            f"Ensemble precondition failed: {split} prediction files missing for {missing}"
        )
    reference_name = MEMBER_MODELS[0]
    reference = frames[reference_name]
    keys = ["unit", "step"]
    required = {"unit", "step", "y_true_raw", "y_true_clipped", "y_pred"}
    if required - set(reference.columns):
        raise ValueError(f"{reference_name} prediction file lacks {sorted(required - set(reference.columns))}")
    for name, frame in frames.items():
        if required - set(frame.columns):
            raise ValueError(f"{name} prediction file lacks {sorted(required - set(frame.columns))}")
        if not frame[keys].equals(reference[keys]):
            raise ValueError(f"Prediction alignment mismatch in {split}: {name} unit/step rows differ")
        for target in ("y_true_raw", "y_true_clipped"):
            if not np.array_equal(frame[target].to_numpy(), reference[target].to_numpy()):
                raise ValueError(f"Prediction alignment mismatch in {split}: {name} {target} differs")
    matrix = np.column_stack([frames[name].y_pred.to_numpy(dtype=float) for name in frames])
    if not np.isfinite(matrix).all():
        raise ValueError(f"Non-finite member predictions found in {split}")
    return list(frames), missing, reference, matrix


def _prediction_frame(
    reference: pd.DataFrame, predictions: np.ndarray, split: str
) -> pd.DataFrame:
    """Build the common prediction output schema for one ensemble method."""
    raw = reference.y_true_raw.to_numpy(dtype=float)
    return pd.DataFrame({
        "unit": reference.unit.to_numpy(dtype=int),
        "step": reference.step.to_numpy(dtype=int),
        "y_true_raw": raw,
        "y_true_clipped": reference.y_true_clipped.to_numpy(dtype=float),
        "y_pred": predictions,
        "error": predictions - raw,
        "split": split,
    })


def _metrics(
    reference: pd.DataFrame, predictions: np.ndarray, rul_cap: float
) -> dict[str, dict[str, float | int]]:
    """Score one method against clipped validation and both official test targets."""
    return evaluate_predictions(
        reference.y_true_clipped.to_numpy(dtype=float), predictions,
        reference.y_true_raw.to_numpy(dtype=float), predictions, rul_cap=rul_cap,
    )


def _correlations(predictions: np.ndarray, truth: np.ndarray, members: list[str]) -> dict[str, dict[str, float]]:
    """Return Pearson correlation between each pair of validation errors."""
    errors = predictions - truth[:, None]
    frame = pd.DataFrame(errors, columns=members)
    return {
        name: {other: float(value) for other, value in row.items()}
        for name, row in frame.corr(method="pearson").iterrows()
    }


def train_one(dataset: str, seed: int, config: dict[str, Any]) -> dict[str, Any]:
    """Fit both ensemble methods on validation predictions and report test metrics."""
    dataset = get_dataset_spec(dataset).dataset
    seed_everything(seed)
    members, excluded, val_reference, x_val = _read_member_predictions(dataset, seed, "val")
    test_members, test_excluded, test_reference, x_test = _read_member_predictions(dataset, seed, "test")
    if members != test_members or excluded != test_excluded:
        raise ValueError("Validation and test member lists differ")
    val_truth = val_reference.y_true_clipped.to_numpy(dtype=float)
    started = time.perf_counter()
    fitted = fit_ensembles(
        x_val, val_truth, float(config["stacking"]["alpha"])
    )
    elapsed = time.perf_counter() - started
    predictions = {
        "weighted_average": {
            "val": fitted.weighted_validation,
            "test": apply_weighted(x_test, fitted.weighted_weights),
        },
        "stacking": {
            "val": fitted.ridge_validation,
            "test": apply_ridge(x_test, fitted.ridge_coefficients, fitted.ridge_intercept),
        },
    }
    scores = {
        method: {
            "val": _metrics(val_reference, values["val"], float(config["rul_cap"]))["val"],
            "test_raw": _metrics(test_reference, values["test"], float(config["rul_cap"]))["test_raw"],
            "test_clipped": _metrics(test_reference, values["test"], float(config["rul_cap"]))["test_clipped"],
        }
        for method, values in predictions.items()
    }
    selected_method = min(scores, key=lambda method: scores[method]["val"]["rmse"])
    selected_params = (
        {"weights": fitted.weighted_weights.tolist()}
        if selected_method == "weighted_average"
        else {
            "coefficients": fitted.ridge_coefficients.tolist(),
            "intercept": fitted.ridge_intercept,
        }
    )
    LOG.info("Validation-selected official method: %s", selected_method)
    LOG.info("Weighted-average weights: %s", dict(zip(members, fitted.weighted_weights.tolist())))
    LOG.info("Positive Ridge coefficients: %s; intercept=%.8f", dict(zip(members, fitted.ridge_coefficients.tolist())), fitted.ridge_intercept)
    for method, method_scores in scores.items():
        for split, values in method_scores.items():
            LOG.info("%s %s RMSE=%.4f MAE=%.4f MSE=%.4f NASA=%.4f R2=%.4f", method, split, values["rmse"], values["mae"], values["mse"], values["nasa_score"], values["r2"])

    output = MODEL_DIR / "outputs" / dataset / f"seed_{seed}"
    output.mkdir(parents=True, exist_ok=True)
    for method, values in predictions.items():
        _prediction_frame(val_reference, values["val"], "val").to_csv(
            output / f"predictions_val_{method}.csv", index=False
        )
        _prediction_frame(test_reference, values["test"], "test").to_csv(
            output / f"predictions_test_{method}.csv", index=False
        )
    _prediction_frame(
        val_reference, predictions[selected_method]["val"], "val"
    ).to_csv(output / "predictions_val.csv", index=False)
    _prediction_frame(
        test_reference, predictions[selected_method]["test"], "test"
    ).to_csv(output / "predictions_test.csv", index=False)

    base_config = dict(config)
    base_config.update({
        "dataset": dataset, "seed": seed, "members": members,
        "excluded_models": excluded, "selected_method": selected_method,
        "selected_parameters": selected_params,
        "weighted_average_weights": dict(zip(members, fitted.weighted_weights.tolist())),
        "stacking_coefficients": dict(zip(members, fitted.ridge_coefficients.tolist())),
        "stacking_intercept": fitted.ridge_intercept,
        "validation_rmse": {method: value["val"]["rmse"] for method, value in scores.items()},
        "alignment_verified": True,
    })
    config_hash = _stable_hash(base_config)
    (output / "config_used.yaml").write_text(yaml.safe_dump(base_config, sort_keys=False), encoding="utf-8")
    params = {
        "dataset": dataset, "seed": seed, "members": members,
        "excluded_models": excluded, "selected_method": selected_method,
        "selected_parameters": selected_params,
        "weighted_average_weights": dict(zip(members, fitted.weighted_weights.tolist())),
        "stacking_coefficients": dict(zip(members, fitted.ridge_coefficients.tolist())),
        "stacking_intercept": fitted.ridge_intercept,
    }
    (output / "best_model.json").write_text(json.dumps(params, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    correlations = _correlations(x_val, val_truth, members)
    history_rows = [
        {"method": method, "split": split, **values}
        for method, method_scores in scores.items()
        for split, values in method_scores.items()
    ]
    pd.DataFrame(history_rows).to_csv(output / "history.csv", index=False)
    metrics_payload = {
        "dataset": dataset, "model": "08_ensemble", "seed": seed,
        "selected_method": selected_method, "metrics_by_method": scores,
        "metrics": scores[selected_method], "validation_error_correlations": correlations,
        "members": members, "excluded_models": excluded,
        "weighted_average_weights": dict(zip(members, fitted.weighted_weights.tolist())),
        "stacking_coefficients": dict(zip(members, fitted.ridge_coefficients.tolist())),
        "stacking_intercept": fitted.ridge_intercept,
        "n_params": len(selected_params.get("weights", selected_params.get("coefficients", [])))
        + int(selected_method == "stacking"),
        "train_seconds": elapsed, "device": "cpu",
        "config_hash": config_hash,
    }
    (output / "metrics.json").write_text(json.dumps(metrics_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for method in predictions:
        plot_prediction_diagnostics(
            val_truth, predictions[method]["val"], output / "figures" / method / "validation",
            val_reference.unit.to_numpy(),
        )
        plot_prediction_diagnostics(
            test_reference.y_true_raw.to_numpy(dtype=float), predictions[method]["test"],
            output / "figures" / method / "test_raw", test_reference.unit.to_numpy(),
        )
        plot_prediction_diagnostics(
            test_reference.y_true_clipped.to_numpy(dtype=float), predictions[method]["test"],
            output / "figures" / method / "test_clipped", test_reference.unit.to_numpy(),
        )
    correlation_frame = pd.DataFrame(correlations, dtype=float)
    correlation_frame.to_csv(output / "validation_error_correlations.csv", index_label="model")
    main_score = scores[selected_method]
    timestamp = datetime.now(timezone.utc).isoformat()
    rows = [
        {
            "track": "CMAPSS", "dataset": dataset, "model": "08_ensemble",
            "seed": seed, "split": split, "level": level,
            "target_type": target, **values,
            "n_params": metrics_payload["n_params"], "train_seconds": elapsed,
            "device": "cpu", "config_hash": config_hash, "timestamp": timestamp,
        }
        for split, level, target, values in (
            ("val", "window", "clipped", main_score["val"]),
            ("test", "engine", "raw", main_score["test_raw"]),
            ("test", "engine", "clipped", main_score["test_clipped"]),
        )
    ]
    record_results(rows)
    _write_ensemble_report(output / "ensemble_report.md", members, excluded, selected_method, scores, correlations, fitted)
    return metrics_payload


def _write_ensemble_report(
    path: Path, members: list[str], excluded: list[str], selected: str,
    scores: dict[str, Any], correlations: dict[str, dict[str, float]], fitted: Any,
) -> None:
    """Write both method metrics, validation selection, weights, and error diversity."""
    lines = [
        "# Ensemble methods", "", f"Official method selected by validation RMSE: **{selected}**.",
        "", f"Included members: {', '.join(members)}.",
        f"Excluded models: {', '.join(excluded) if excluded else 'none'}.", "",
        "## Validation-fitted parameters", "",
        f"Weighted-average weights: `{dict(zip(members, fitted.weighted_weights.tolist()))}`",
        f"Positive Ridge coefficients: `{dict(zip(members, fitted.ridge_coefficients.tolist()))}`",
        f"Positive Ridge intercept: `{fitted.ridge_intercept:.8f}`", "",
        "## Metrics", "", "| Method | Split | RMSE | MAE | MSE | NASA score | R² |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for method, method_scores in scores.items():
        for split, values in method_scores.items():
            lines.append(
                f"| {method} | {split} | {values['rmse']:.4f} | {values['mae']:.4f} | "
                f"{values['mse']:.4f} | {values['nasa_score']:.4f} | {values['r2']:.4f} |"
            )
    lines.extend(["", "## Validation member error correlations", ""])
    lines.append("| Model | " + " | ".join(members) + " |")
    lines.append("|---|" + "---:|" * len(members))
    for member, row in correlations.items():
        lines.append("| " + member + " | " + " | ".join(f"{row[name]:.4f}" for name in members) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse dataset and seed options; epochs is accepted for workflow consistency."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=(*DATASET_IDS, "all"), default="FD001")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--epochs", type=int, help="Accepted for command compatibility; ensembles have no epochs")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Fit ensembles for requested dataset and seed combinations."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    config = load_config(args.config)
    seeds = args.seeds if args.seeds else [args.seed]
    datasets = DATASET_IDS if args.dataset == "all" else (args.dataset,)
    for dataset in datasets:
        for seed in seeds:
            train_one(dataset, seed, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
