"""Train and evaluate the CMAPSS LightGBM baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODEL_DIR = Path(__file__).resolve().parent
TRACK_ROOT = MODEL_DIR.parents[1]
sys.path.insert(0, str(TRACK_ROOT)) if str(TRACK_ROOT) not in sys.path else None
os.environ.setdefault("MPLCONFIGDIR", str(TRACK_ROOT.parents[0] / ".venv" / "mplconfig"))

import lightgbm as lgb
import numpy as np
import pandas as pd
import torch
import yaml
from lightgbm.basic import _LIB

from common.config import DATASET_IDS, cmapss_root, get_dataset_spec
from common.data import CMapssData, load_cmapss_dataset
from common.evaluate import evaluate_predictions
from common.features import FEATURE_SUFFIXES, features_from_window_set
from common.metrics import compute_metrics
from common.plots import plot_metric_history, plot_prediction_diagnostics
from common.preprocess import CMapssPreprocessor
from common.report import record_results
from common.splits import EngineSplit, get_or_create_split, split_to_dict
from common.windows import WindowSet, make_test_last_windows, make_windows

from model import aggregate_channel_contributions, build_regressor, config_hash, count_leaf_values

LOG = logging.getLogger("lightgbm_train")


@dataclass
class PreparedData:
    """Leakage-safe transformed windows used for fit and validation scoring."""

    source: CMapssData
    split: EngineSplit
    preprocessor: CMapssPreprocessor
    train_windows: WindowSet
    val_windows: WindowSet
    test_windows: WindowSet
    x_train: pd.DataFrame
    x_val: pd.DataFrame
    x_test: pd.DataFrame
    y_test_raw: np.ndarray
    y_test_clipped: np.ndarray
    artifacts_dir: Path


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load the model configuration YAML from this folder or a supplied path."""
    config_path = Path(path) if path is not None else MODEL_DIR / "config.yaml"
    value = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Configuration at {config_path} must contain a YAML mapping")
    return value


def _runtime_device(requested: str) -> str:
    """Resolve the available training backend and explain the LightGBM CPU build."""
    has_gpu_backend = hasattr(_LIB, "LGBM_GetGPUDeviceCount") or hasattr(_LIB, "LGBM_GetCUDADeviceCount")
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    if requested in {"cuda", "gpu"} and not has_gpu_backend:
        raise RuntimeError("This installed LightGBM wheel has no GPU/CUDA backend; choose --device cpu or auto.")
    if requested in {"cuda", "gpu"}:
        return "cuda" if requested == "cuda" else "gpu"
    if requested == "auto" and gpu_name:
        LOG.warning("Detected %s, but this LightGBM wheel has no GPU/CUDA backend; fitting on CPU.", gpu_name)
    elif requested == "auto" and not gpu_name:
        LOG.warning("CUDA is unavailable; fitting LightGBM on CPU.")
    return "cpu"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically, creating the containing directory first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def prepare_dataset(dataset: str, config: dict[str, Any]) -> PreparedData:
    """Load data, fit preprocessing on train engines, and build shared windows."""
    spec = get_dataset_spec(dataset)
    source = load_cmapss_dataset(spec.dataset, rul_cap=int(config["rul_cap"]))
    split = get_or_create_split(
        spec.dataset,
        source.train["unit"].astype(int).unique().tolist(),
        val_fraction=float(config["val_fraction"]),
        seed=int(config["split_seed"]),
    )
    preprocessor = CMapssPreprocessor(spec.dataset).fit(source.train, split.train_units)
    transformed_train = preprocessor.transform(source.train)
    transformed_test = preprocessor.transform(source.test)
    train_rows = transformed_train.loc[transformed_train["unit"].isin(split.train_units)]
    val_rows = transformed_train.loc[transformed_train["unit"].isin(split.val_units)]
    window_length = int(config["window_length"])
    stride = int(config["stride"])
    train_windows = make_windows(train_rows, preprocessor.feature_columns, window_length, stride)
    val_windows = make_windows(val_rows, preprocessor.feature_columns, window_length, stride)
    test_windows = make_test_last_windows(transformed_test, preprocessor.feature_columns, window_length)
    include_condition = preprocessor.n_conditions > 1
    x_train = features_from_window_set(
        train_windows.x,
        preprocessor.feature_columns,
        train_windows.condition_ids if include_condition else None,
    )
    x_val = features_from_window_set(
        val_windows.x,
        preprocessor.feature_columns,
        val_windows.condition_ids if include_condition else None,
    )
    x_test = features_from_window_set(
        test_windows.x,
        preprocessor.feature_columns,
        test_windows.condition_ids if include_condition else None,
    )
    truth = source.test_truth.set_index("unit").loc[test_windows.units]
    artifacts_dir = cmapss_root() / "results" / "artifacts" / spec.dataset
    preprocessor.save(artifacts_dir / "preprocessor.joblib")
    _write_json(artifacts_dir / "split_ids.json", split_to_dict(split))
    _write_json(
        artifacts_dir / "feature_config.json",
        {
            "window_length": window_length,
            "stride": stride,
            "channels": list(preprocessor.feature_columns),
            "feature_suffixes": list(FEATURE_SUFFIXES),
            "include_condition_id": include_condition,
            "feature_names": x_train.columns.tolist(),
        },
    )
    LOG.info("Dropped constant sensors in the training-engine split: %s", list(preprocessor.dropped_sensors))
    LOG.info(
        "Built windows: train=%d engines/%d windows, val=%d engines/%d windows, test=%d engines/%d padded",
        len(split.train_units),
        len(train_windows),
        len(split.val_units),
        len(val_windows),
        len(test_windows),
        test_windows.padded_engines,
    )
    return PreparedData(
        source,
        split,
        preprocessor,
        train_windows,
        val_windows,
        test_windows,
        x_train,
        x_val,
        x_test,
        truth["rul_raw"].to_numpy(dtype=float),
        truth["rul_clipped"].to_numpy(dtype=float),
        artifacts_dir,
    )


def _fit_model(
    prepared: PreparedData,
    config: dict[str, Any],
    seed: int,
) -> tuple[lgb.LGBMRegressor, dict[str, dict[str, list[float]]], float]:
    """Fit one model with early stopping against validation RMSE."""
    estimator = build_regressor(config, seed)
    evaluations: dict[str, dict[str, list[float]]] = {}
    started = time.perf_counter()
    estimator.fit(
        prepared.x_train,
        prepared.train_windows.y,
        eval_set=[(prepared.x_train, prepared.train_windows.y), (prepared.x_val, prepared.val_windows.y)],
        eval_names=["train", "val"],
        eval_metric="rmse",
        callbacks=[
            lgb.early_stopping(int(config["early_stopping_rounds"]), verbose=False),
            lgb.log_evaluation(period=0),
            lgb.record_evaluation(evaluations),
        ],
    )
    return estimator, evaluations, time.perf_counter() - started


def _tune_parameters(
    prepared: PreparedData,
    config: dict[str, Any],
    seed: int,
    trials: int = 40,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Find parameters using validation RMSE only and retain every trial."""
    import optuna

    records: list[dict[str, Any]] = []

    def objective(trial: optuna.Trial) -> float:
        trial_config = dict(config)
        trial_config.update(
            {
                "num_leaves": trial.suggest_int("num_leaves", 15, 127),
                "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 5, 100),
                "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
                "lambda_l2": trial.suggest_float("lambda_l2", 1e-3, 10.0, log=True),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            }
        )
        estimator, _, _ = _fit_model(prepared, trial_config, seed)
        value = float(estimator.best_score_["val"]["rmse"])
        record = {"trial": trial.number, "val_rmse": value, "best_iteration": int(estimator.best_iteration_)}
        record.update(trial.params)
        records.append(record)
        return value

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=trials, show_progress_bar=False)
    tuned = dict(config)
    tuned.update(study.best_params)
    return tuned, pd.DataFrame(records).sort_values("trial").reset_index(drop=True)


def _prediction_frame(
    units: np.ndarray,
    steps: np.ndarray,
    y_raw: np.ndarray,
    y_clipped: np.ndarray,
    y_pred: np.ndarray,
    split: str,
) -> pd.DataFrame:
    """Build a Phase A predictions CSV with raw and capped truth values."""
    return pd.DataFrame(
        {
            "unit": units.astype(int),
            "step": steps.astype(int),
            "y_true_raw": y_raw.astype(float),
            "y_true_clipped": y_clipped.astype(float),
            "y_pred": y_pred.astype(float),
            "error": y_pred.astype(float) - y_raw.astype(float),
            "split": split,
        }
    )


def _save_explanations(estimator: lgb.LGBMRegressor, prepared: PreparedData, output_dir: Path) -> None:
    """Write feature gain and mean absolute grouped prediction contributions."""
    booster = estimator.booster_
    best_iteration = estimator.best_iteration_ or 0
    importance = pd.DataFrame(
        {
            "feature": prepared.x_train.columns,
            "gain": booster.feature_importance(importance_type="gain", iteration=best_iteration),
            "split": booster.feature_importance(importance_type="split", iteration=best_iteration),
        }
    ).sort_values("gain", ascending=False)
    importance.to_csv(output_dir / "feature_importance.csv", index=False)
    contribution = booster.predict(prepared.x_test, pred_contrib=True, num_iteration=best_iteration)
    grouped = aggregate_channel_contributions(
        contribution,
        prepared.x_test.columns.tolist(),
        prepared.preprocessor.feature_columns,
    )
    pd.DataFrame(grouped).to_csv(output_dir / "top_contributors.csv", index=False)


def train_one(
    dataset: str,
    seed: int,
    config: dict[str, Any],
    device_request: str = "auto",
    tuned: bool = False,
    w50_ablation: bool = False,
) -> dict[str, Any]:
    """Train one dataset/seed, save artifacts, score results, and refresh reports."""
    dataset = get_dataset_spec(dataset).dataset
    device = _runtime_device(device_request)
    config = dict(config)
    config["device_type"] = device
    prepared = prepare_dataset(dataset, config)
    estimator, evaluations, train_seconds = _fit_model(prepared, config, seed)
    best_iteration = int(estimator.best_iteration_ or int(config["n_estimators"]))
    val_pred = np.asarray(estimator.predict(prepared.x_val, num_iteration=best_iteration), dtype=float)
    test_pred = np.asarray(estimator.predict(prepared.x_test, num_iteration=best_iteration), dtype=float)
    scores = evaluate_predictions(
        prepared.val_windows.y,
        val_pred,
        prepared.y_test_raw,
        test_pred,
        rul_cap=float(config["rul_cap"]),
    )
    model_name = "01_lightgbm_tuned" if tuned else "01_lightgbm_w50" if w50_ablation else "01_lightgbm"
    output_root = MODEL_DIR / "outputs_tuned" if tuned else MODEL_DIR / "outputs_w50" if w50_ablation else MODEL_DIR / "outputs"
    output_dir = output_root / dataset / f"seed_{seed}"
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    config_used = dict(config)
    config_used.update({"dataset": dataset, "seed": seed, "model": model_name, "device": device})
    config_hash_value = config_hash(config_used)
    (output_dir / "config_used.yaml").write_text(
        yaml.safe_dump(config_used, sort_keys=False), encoding="utf-8"
    )
    model_path = output_dir / "model.txt"
    estimator.booster_.save_model(str(model_path), num_iteration=best_iteration)
    n_params = count_leaf_values(estimator.booster_, num_iteration=best_iteration)

    val_frame = _prediction_frame(
        prepared.val_windows.units,
        prepared.val_windows.steps,
        prepared.val_windows.y_raw if prepared.val_windows.y_raw is not None else prepared.val_windows.y,
        prepared.val_windows.y,
        val_pred,
        "val",
    )
    test_frame = _prediction_frame(
        prepared.test_windows.units,
        prepared.test_windows.steps,
        prepared.y_test_raw,
        prepared.y_test_clipped,
        test_pred,
        "test",
    )
    val_frame.to_csv(output_dir / "predictions_val.csv", index=False)
    test_frame.to_csv(output_dir / "predictions_test.csv", index=False)
    _save_explanations(estimator, prepared, output_dir)

    train_curve = evaluations.get("train", {}).get("rmse", [])
    val_curve = evaluations.get("val", {}).get("rmse", [])
    if train_curve and val_curve:
        iterations = min(len(train_curve), len(val_curve))
        history = pd.DataFrame(
            {
                "iteration": np.arange(1, iterations + 1),
                "train_rmse": train_curve[:iterations],
                "val_rmse": val_curve[:iterations],
            }
        )
        history.to_csv(output_dir / "history.csv", index=False)
        plot_metric_history(history, "iteration", "train_rmse", "val_rmse", figures_dir / "loss_curve.png", "RMSE (cycles)")
    plot_prediction_diagnostics(
        prepared.val_windows.y,
        val_pred,
        figures_dir / "validation",
        prepared.val_windows.units,
    )
    plot_prediction_diagnostics(
        prepared.y_test_raw,
        test_pred,
        figures_dir / "test_raw",
        prepared.test_windows.units,
    )
    metrics_payload = {
        "dataset": dataset,
        "model": model_name,
        "seed": seed,
        "device": device,
        "metrics": scores,
        "n_params": n_params,
        "train_seconds": train_seconds,
        "best_iteration": best_iteration,
        "padded_test_engines": prepared.test_windows.padded_engines,
        "dropped_constant_sensors": list(prepared.preprocessor.dropped_sensors),
        "config_hash": config_hash_value,
    }
    _write_json(output_dir / "metrics.json", metrics_payload)
    feature_hash = hashlib.sha256(("\n".join(prepared.x_train.columns)).encode("utf-8")).hexdigest()
    rows: list[dict[str, Any]] = []
    metric_specs = (
        ("val", "window", "clipped", scores["val"]),
        ("test", "engine", "raw", scores["test_raw"]),
        ("test", "engine", "clipped", scores["test_clipped"]),
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    for split_name, level, target_type, metric_values in metric_specs:
        rows.append(
            {
                "track": "CMAPSS",
                "dataset": dataset,
                "model": model_name,
                "seed": seed,
                "split": split_name,
                "level": level,
                "target_type": target_type,
                **metric_values,
                "n_params": n_params,
                "train_seconds": train_seconds,
                "device": device,
                "config_hash": config_hash_value,
                "timestamp": timestamp,
            }
        )
    record_results(rows)
    return {
        "dataset": dataset,
        "model": model_name,
        "seed": seed,
        "output_dir": output_dir,
        "metrics": scores,
        "n_params": n_params,
        "train_seconds": train_seconds,
        "device": device,
        "best_iteration": best_iteration,
        "config_hash": config_hash_value,
        "padded_test_engines": prepared.test_windows.padded_engines,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the baseline training command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=(*DATASET_IDS, "all"), default="FD001")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "gpu"), default="auto")
    parser.add_argument("--epochs", type=int, help="Override n_estimators for a short/debug run")
    parser.add_argument("--tune", action="store_true", help="Run 40 Optuna trials using validation RMSE only")
    parser.add_argument(
        "--w50-ablation", action="store_true",
        help="Run isolated 50-cycle-window ablation; all other LightGBM settings stay unchanged",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run requested dataset(s) and seed(s), then print actual split metrics."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    config = load_config(args.config)
    if args.w50_ablation:
        if args.tune:
            raise ValueError("--w50-ablation cannot be combined with --tune")
        config["window_length"] = 50
    if args.epochs is not None:
        if args.epochs <= 0:
            raise ValueError("--epochs must be positive")
        config["n_estimators"] = args.epochs
    seeds = args.seeds if args.seeds else [args.seed]
    datasets = DATASET_IDS if args.dataset == "all" else (args.dataset,)
    completed: list[dict[str, Any]] = []
    for dataset in datasets:
        for seed in seeds:
            run_config = dict(config)
            run_config["seed"] = seed
            if args.tune:
                prepared = prepare_dataset(dataset, run_config)
                tuned_config, tuning_log = _tune_parameters(prepared, run_config, seed)
                (MODEL_DIR / "outputs_tuned" / dataset / f"seed_{seed}").mkdir(parents=True, exist_ok=True)
                tuning_log.to_csv(MODEL_DIR / "outputs_tuned" / dataset / f"seed_{seed}" / "tuning_log.csv", index=False)
                tuned_config["seed"] = seed
                (MODEL_DIR / "config_tuned.yaml").write_text(yaml.safe_dump(tuned_config, sort_keys=False), encoding="utf-8")
                result = train_one(dataset, seed, tuned_config, args.device, tuned=True)
            else:
                result = train_one(dataset, seed, run_config, args.device, w50_ablation=args.w50_ablation)
            completed.append(result)
            for split_name, metrics in result["metrics"].items():
                LOG.info(
                    "%s %s seed=%d %s RMSE=%.4f MAE=%.4f MSE=%.4f NASA=%.4f R2=%.4f",
                    result["model"],
                    result["dataset"],
                    result["seed"],
                    split_name,
                    metrics["rmse"],
                    metrics["mae"],
                    metrics["mse"],
                    metrics["nasa_score"],
                    metrics["r2"],
                )
    return 0 if completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
