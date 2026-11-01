"""Train and evaluate the C-MAPSS LSTM RUL model."""

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
os.environ.setdefault(
    "MPLCONFIGDIR", str(TRACK_ROOT.parents[0] / ".venv" / "mplconfig")
)

import numpy as np
import pandas as pd
import torch
import yaml

from common.config import DATASET_IDS, cmapss_root, get_dataset_spec
from common.data import CMapssData, load_cmapss_dataset, load_train
from common.evaluate import evaluate_predictions
from common.metrics import compute_metrics
from common.plots import plot_loss_curve, plot_prediction_diagnostics
from common.preprocess import CMapssPreprocessor
from common.report import record_results
from common.splits import EngineSplit, get_or_create_split, split_to_dict
from common.train_utils import (
    make_data_loader,
    seed_everything,
    select_device,
    train_deep_model,
)
from common.windows import (
    WindowDataset,
    WindowSet,
    make_test_last_windows,
    make_windows,
)

_MODEL_SPEC = importlib.util.spec_from_file_location(
    "sire_cmapss_02_lstm_model", MODEL_DIR / "model.py"
)
if _MODEL_SPEC is None or _MODEL_SPEC.loader is None:
    raise ImportError(
        f"Cannot load LSTM model definition from {MODEL_DIR / 'model.py'}"
    )
_MODEL_MODULE = importlib.util.module_from_spec(_MODEL_SPEC)
sys.modules[_MODEL_SPEC.name] = _MODEL_MODULE
_MODEL_SPEC.loader.exec_module(_MODEL_MODULE)
LSTMRegressor = _MODEL_MODULE.LSTMRegressor
build_model = _MODEL_MODULE.build_model

LOG = logging.getLogger("lstm_train")


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load model settings from this folder or a supplied YAML file."""
    config_path = Path(path) if path is not None else MODEL_DIR / "config.yaml"
    value = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Configuration at {config_path} must contain a YAML mapping")
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically after creating its parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _config_hash(config: dict[str, Any]) -> str:
    """Hash a stable JSON representation of the full run configuration."""
    encoded = json.dumps(
        config, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def prepare_dataset(
    dataset: str, config: dict[str, Any]
) -> tuple[
    CMapssData,
    EngineSplit,
    CMapssPreprocessor,
    WindowSet,
    WindowSet,
    WindowSet,
    np.ndarray,
    np.ndarray,
]:
    """Build normalized train, validation, and test windows on the shared split."""
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
    train_rows = transformed_train.loc[
        transformed_train["unit"].isin(split.train_units)
    ]
    val_rows = transformed_train.loc[transformed_train["unit"].isin(split.val_units)]
    train_windows = make_windows(
        train_rows,
        preprocessor.feature_columns,
        window_length=int(config["window_length"]),
        stride=int(config["stride"]),
    )
    val_windows = make_windows(
        val_rows,
        preprocessor.feature_columns,
        window_length=int(config["window_length"]),
        stride=int(config["stride"]),
    )
    test_windows = make_test_last_windows(
        transformed_test,
        preprocessor.feature_columns,
        window_length=int(config["window_length"]),
    )
    truth = source.test_truth.set_index("unit").loc[test_windows.units]
    artifacts_dir = cmapss_root() / "results" / "artifacts" / spec.dataset
    preprocessor.save(artifacts_dir / "preprocessor.joblib")
    split_path = artifacts_dir / "split_ids.json"
    split_path.write_text(
        json.dumps(split_to_dict(split), indent=2) + "\n", encoding="utf-8"
    )
    LOG.info(
        "Prepared %s: train=%d engines/%d windows, val=%d engines/%d windows, "
        "test=%d engines (%d padded); channels=%d",
        spec.dataset,
        len(split.train_units),
        len(train_windows),
        len(split.val_units),
        len(val_windows),
        len(test_windows),
        test_windows.padded_engines,
        len(preprocessor.feature_columns),
    )
    LOG.info(
        "Dropped constant sensors in training split: %s",
        list(preprocessor.dropped_sensors),
    )
    return (
        source,
        split,
        preprocessor,
        train_windows,
        val_windows,
        test_windows,
        truth["rul_raw"].to_numpy(dtype=float),
        truth["rul_clipped"].to_numpy(dtype=float),
    )


def _predict(
    model: LSTMRegressor,
    windows: WindowSet,
    device: torch.device,
    batch_size: int,
    seed: int,
    cap: float,
) -> np.ndarray:
    """Predict windows in batches and convert scaled outputs back to cycles."""
    loader = make_data_loader(
        WindowDataset(WindowSet(windows.x, None, windows.units, windows.steps)),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        seed=seed,
        device=device,
    )
    model.eval()
    predictions: list[np.ndarray] = []
    with torch.inference_mode():
        for batch in loader:
            inputs = batch.to(device, non_blocking=True)
            predictions.append((model(inputs).reshape(-1) * cap).cpu().numpy())
    if not predictions:
        raise ValueError("Cannot predict an empty window set")
    return np.concatenate(predictions).astype(float, copy=False)


def _prepare_validation_only(dataset: str, config: dict[str, Any]) -> tuple[
    EngineSplit, CMapssPreprocessor, WindowSet, WindowSet
]:
    """Prepare train/validation windows without loading or examining test data."""
    spec = get_dataset_spec(dataset)
    train_frame = load_train(
        cmapss_root() / "data" / spec.train_filename,
        rul_cap=int(config["rul_cap"]),
    )
    split = get_or_create_split(
        spec.dataset,
        train_frame["unit"].astype(int).unique().tolist(),
        val_fraction=float(config["val_fraction"]),
        seed=int(config["split_seed"]),
    )
    preprocessor = CMapssPreprocessor(spec.dataset).fit(train_frame, split.train_units)
    transformed = preprocessor.transform(train_frame)
    train_rows = transformed.loc[transformed["unit"].isin(split.train_units)]
    val_rows = transformed.loc[transformed["unit"].isin(split.val_units)]
    train_windows = make_windows(
        train_rows,
        preprocessor.feature_columns,
        window_length=int(config["window_length"]),
        stride=int(config["stride"]),
    )
    val_windows = make_windows(
        val_rows,
        preprocessor.feature_columns,
        window_length=int(config["window_length"]),
        stride=int(config["stride"]),
    )
    return split, preprocessor, train_windows, val_windows


def tune_on_validation(
    dataset: str,
    seed: int,
    config: dict[str, Any],
    device_request: str = "auto",
) -> tuple[dict[str, Any], str]:
    """Compare the baseline config with a small, logged validation-only sweep."""
    dataset = get_dataset_spec(dataset).dataset
    result_dir = MODEL_DIR / "outputs" / dataset / f"seed_{seed}"
    metrics_path = result_dir / "metrics.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(
            "Run the default LSTM training before validation tuning"
        )
    initial_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if (
        initial_metrics.get("model") != "02_lstm"
        or int(initial_metrics.get("seed", -1)) != seed
    ):
        raise ValueError(
            f"Existing metrics at {metrics_path} do not match this model and seed"
        )

    records: list[dict[str, Any]] = []
    initial_config = dict(config)
    records.append(
        {
            "trial": "default",
            "hidden_size": int(initial_config["hidden_size"]),
            "num_layers": int(initial_config["num_layers"]),
            "lstm_dropout": float(initial_config["lstm_dropout"]),
            "head_dropout": float(initial_config["head_dropout"]),
            "window_length": int(initial_config["window_length"]),
            "val_rmse": float(initial_metrics["metrics"]["val"]["rmse"]),
            "val_mae": float(initial_metrics["metrics"]["val"]["mae"]),
            "val_mse": float(initial_metrics["metrics"]["val"]["mse"]),
            "val_nasa_score": float(initial_metrics["metrics"]["val"]["nasa_score"]),
            "val_r2": float(initial_metrics["metrics"]["val"]["r2"]),
            "best_epoch": int(initial_metrics["best_epoch"]),
            "epochs_completed": int(initial_metrics["epochs_completed"]),
            "train_seconds": float(initial_metrics["train_seconds"]),
        }
    )
    candidates = (
        (
            "h128_l1_d02_w30",
            {
                "hidden_size": 128,
                "num_layers": 1,
                "lstm_dropout": 0.2,
                "window_length": 30,
            },
        ),
        (
            "h128_l2_d02_w30",
            {
                "hidden_size": 128,
                "num_layers": 2,
                "lstm_dropout": 0.2,
                "window_length": 30,
            },
        ),
        (
            "h128_l2_d03_w30",
            {
                "hidden_size": 128,
                "num_layers": 2,
                "lstm_dropout": 0.3,
                "window_length": 30,
            },
        ),
        (
            "h128_l2_d04_w30",
            {
                "hidden_size": 128,
                "num_layers": 2,
                "lstm_dropout": 0.4,
                "window_length": 30,
            },
        ),
        (
            "h128_l3_d02_w30",
            {
                "hidden_size": 128,
                "num_layers": 3,
                "lstm_dropout": 0.2,
                "window_length": 30,
            },
        ),
        (
            "h128_l2_d03_w40",
            {
                "hidden_size": 128,
                "num_layers": 2,
                "lstm_dropout": 0.3,
                "window_length": 40,
            },
        ),
        (
            "h128_l2_d03_w50",
            {
                "hidden_size": 128,
                "num_layers": 2,
                "lstm_dropout": 0.3,
                "window_length": 50,
            },
        ),
    )
    trial_root = result_dir / "tuning_trials"
    for trial_name, overrides in candidates:
        trial_config = dict(config)
        trial_config.update(overrides)
        trial_config.update({"dataset": dataset, "seed": seed, "model": "02_lstm"})
        split, preprocessor, train_windows, val_windows = _prepare_validation_only(
            dataset, trial_config
        )
        device = select_device(device_request)
        seed_everything(seed)
        train_loader = make_data_loader(
            WindowDataset(train_windows),
            batch_size=int(trial_config["batch_size"]),
            shuffle=True,
            num_workers=int(trial_config["num_workers"]),
            seed=seed,
            device=device,
        )
        val_loader = make_data_loader(
            WindowDataset(val_windows),
            batch_size=int(trial_config["batch_size"]),
            shuffle=False,
            num_workers=int(trial_config["num_workers"]),
            seed=seed,
            device=device,
        )
        model = build_model(len(preprocessor.feature_columns), trial_config)
        trial_dir = trial_root / trial_name
        trial_config["trial"] = trial_name
        trial_config["train_engines"] = len(split.train_units)
        trial_config["validation_engines"] = len(split.val_units)
        trial_config["train_windows"] = len(train_windows)
        trial_config["validation_windows"] = len(val_windows)
        trial_dir.mkdir(parents=True, exist_ok=True)
        (trial_dir / "config_used.yaml").write_text(
            yaml.safe_dump(trial_config, sort_keys=False), encoding="utf-8"
        )
        started = time.perf_counter()
        history = train_deep_model(
            model=model,
            train_loader=train_loader,
            val_loader=val_loader,
            output_dir=trial_dir,
            rul_cap=float(trial_config["rul_cap"]),
            seed=seed,
            device=device,
            learning_rate=float(trial_config["learning_rate"]),
            weight_decay=float(trial_config["weight_decay"]),
            max_epochs=int(trial_config["max_epochs"]),
            patience=int(trial_config["early_stopping_patience"]),
            scheduler_patience=int(trial_config["scheduler_patience"]),
            scheduler_factor=float(trial_config["scheduler_factor"]),
            gradient_clip=float(trial_config["gradient_clip"]),
        )
        train_seconds = time.perf_counter() - started
        val_prediction = _predict(
            model,
            val_windows,
            device,
            int(trial_config["batch_size"]),
            seed,
            float(trial_config["rul_cap"]),
        )
        metrics = compute_metrics(val_windows.y, val_prediction)
        best_epoch = int(history.loc[history["val_rmse"].idxmin(), "epoch"])
        records.append(
            {
                "trial": trial_name,
                "hidden_size": int(overrides["hidden_size"]),
                "num_layers": int(overrides["num_layers"]),
                "lstm_dropout": float(overrides["lstm_dropout"]),
                "head_dropout": float(trial_config["head_dropout"]),
                "window_length": int(overrides["window_length"]),
                "val_rmse": float(metrics["rmse"]),
                "val_mae": float(metrics["mae"]),
                "val_mse": float(metrics["mse"]),
                "val_nasa_score": float(metrics["nasa_score"]),
                "val_r2": float(metrics["r2"]),
                "best_epoch": best_epoch,
                "epochs_completed": len(history),
                "train_seconds": train_seconds,
            }
        )
        LOG.info(
            "validation trial=%s rmse=%.4f best_epoch=%d",
            trial_name,
            metrics["rmse"],
            best_epoch,
        )

    results = pd.DataFrame(records)
    best_index = results["val_rmse"].astype(float).idxmin()
    results["selected"] = False
    results.loc[best_index, "selected"] = True
    results.to_csv(result_dir / "tuning_log.csv", index=False)
    best_trial = str(results.loc[best_index, "trial"])
    selected = results.loc[best_index]
    tuned_config = dict(config)
    tuned_config.update(
        {
            "hidden_size": int(selected["hidden_size"]),
            "num_layers": int(selected["num_layers"]),
            "lstm_dropout": float(selected["lstm_dropout"]),
            "head_dropout": float(selected["head_dropout"]),
            "window_length": int(selected["window_length"]),
        }
    )
    LOG.info(
        "Selected trial=%s by validation RMSE=%.4f",
        best_trial,
        float(selected["val_rmse"]),
    )
    return tuned_config, best_trial


def _prediction_frame(
    units: np.ndarray,
    steps: np.ndarray,
    y_raw: np.ndarray,
    y_clipped: np.ndarray,
    y_pred: np.ndarray,
    split: str,
) -> pd.DataFrame:
    """Build a Phase A prediction CSV with both truth variants and error."""
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


def train_one(
    dataset: str,
    seed: int,
    config: dict[str, Any],
    device_request: str = "auto",
) -> dict[str, Any]:
    """Train one dataset and seed, write outputs, and refresh comparison reports."""
    dataset = get_dataset_spec(dataset).dataset
    run_config = dict(config)
    run_config.update({"dataset": dataset, "seed": int(seed), "model": "02_lstm"})
    prepared = prepare_dataset(dataset, run_config)
    (
        _,
        split,
        preprocessor,
        train_windows,
        val_windows,
        test_windows,
        test_raw,
        test_clipped,
    ) = prepared

    seed_everything(seed)
    device = select_device(device_request)
    train_loader = make_data_loader(
        WindowDataset(train_windows),
        batch_size=int(run_config["batch_size"]),
        shuffle=True,
        num_workers=int(run_config["num_workers"]),
        seed=seed,
        device=device,
    )
    val_loader = make_data_loader(
        WindowDataset(val_windows),
        batch_size=int(run_config["batch_size"]),
        shuffle=False,
        num_workers=int(run_config["num_workers"]),
        seed=seed,
        device=device,
    )
    model = build_model(len(preprocessor.feature_columns), run_config)
    output_dir = MODEL_DIR / "outputs" / dataset / f"seed_{seed}"
    started = time.perf_counter()
    history = train_deep_model(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        output_dir=output_dir,
        rul_cap=float(run_config["rul_cap"]),
        seed=seed,
        device=device,
        learning_rate=float(run_config["learning_rate"]),
        weight_decay=float(run_config["weight_decay"]),
        max_epochs=int(run_config["max_epochs"]),
        patience=int(run_config["early_stopping_patience"]),
        scheduler_patience=int(run_config["scheduler_patience"]),
        scheduler_factor=float(run_config["scheduler_factor"]),
        gradient_clip=float(run_config["gradient_clip"]),
    )
    train_seconds = time.perf_counter() - started
    model.eval()
    val_pred = _predict(
        model,
        val_windows,
        device,
        int(run_config["batch_size"]),
        seed,
        float(run_config["rul_cap"]),
    )
    test_pred = _predict(
        model,
        test_windows,
        device,
        int(run_config["batch_size"]),
        seed,
        float(run_config["rul_cap"]),
    )
    scores = evaluate_predictions(
        val_windows.y,
        val_pred,
        test_raw,
        test_pred,
        rul_cap=float(run_config["rul_cap"]),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    config_used = dict(run_config)
    config_used["device"] = str(device)
    config_used["n_features"] = len(preprocessor.feature_columns)
    config_used["dropped_constant_sensors"] = list(preprocessor.dropped_sensors)
    config_used["train_engines"] = len(split.train_units)
    config_used["validation_engines"] = len(split.val_units)
    config_used["train_windows"] = len(train_windows)
    config_used["validation_windows"] = len(val_windows)
    config_used["padded_test_engines"] = test_windows.padded_engines
    config_used_path = output_dir / "config_used.yaml"
    config_used_path.write_text(
        yaml.safe_dump(config_used, sort_keys=False), encoding="utf-8"
    )
    weights_path = output_dir / "best_model.pt"
    torch.save(
        {name: tensor.detach().cpu() for name, tensor in model.state_dict().items()},
        weights_path,
    )

    val_raw = val_windows.y_raw if val_windows.y_raw is not None else val_windows.y
    _prediction_frame(
        val_windows.units,
        val_windows.steps,
        val_raw,
        val_windows.y,
        val_pred,
        "val",
    ).to_csv(output_dir / "predictions_val.csv", index=False)
    _prediction_frame(
        test_windows.units,
        test_windows.steps,
        test_raw,
        test_clipped,
        test_pred,
        "test",
    ).to_csv(output_dir / "predictions_test.csv", index=False)
    plot_loss_curve(history, figures_dir / "loss_curve.png")
    plot_prediction_diagnostics(
        val_windows.y, val_pred, figures_dir / "validation", val_windows.units
    )
    plot_prediction_diagnostics(
        test_raw, test_pred, figures_dir / "test_raw", test_windows.units
    )
    plot_prediction_diagnostics(
        test_clipped, test_pred, figures_dir / "test_clipped", test_windows.units
    )

    n_params = sum(parameter.numel() for parameter in model.parameters())
    config_hash_value = _config_hash(config_used)
    best_epoch = int(history.loc[history["val_rmse"].idxmin(), "epoch"])
    metrics_payload = {
        "dataset": dataset,
        "model": "02_lstm",
        "seed": seed,
        "device": str(device),
        "metrics": scores,
        "n_params": n_params,
        "train_seconds": train_seconds,
        "best_epoch": best_epoch,
        "epochs_completed": len(history),
        "padded_test_engines": test_windows.padded_engines,
        "dropped_constant_sensors": list(preprocessor.dropped_sensors),
        "config_hash": config_hash_value,
    }
    _write_json(output_dir / "metrics.json", metrics_payload)
    result_rows: list[dict[str, Any]] = []
    timestamp = datetime.now(timezone.utc).isoformat()
    metric_rows = (
        ("val", "window", "clipped", scores["val"]),
        ("test", "engine", "raw", scores["test_raw"]),
        ("test", "engine", "clipped", scores["test_clipped"]),
    )
    for split_name, level, target_type, values in metric_rows:
        result_rows.append(
            {
                "track": "CMAPSS",
                "dataset": dataset,
                "model": "02_lstm",
                "seed": seed,
                "split": split_name,
                "level": level,
                "target_type": target_type,
                **values,
                "n_params": n_params,
                "train_seconds": train_seconds,
                "device": str(device),
                "config_hash": config_hash_value,
                "timestamp": timestamp,
            }
        )
    record_results(result_rows)
    LOG.info(
        "Best epoch=%d/%d; train_seconds=%.2f; parameters=%d",
        best_epoch,
        len(history),
        train_seconds,
        n_params,
    )
    for split_name, values in scores.items():
        LOG.info(
            "%s %s seed=%d RMSE=%.4f MAE=%.4f MSE=%.4f NASA=%.4f R2=%.4f",
            dataset,
            split_name,
            seed,
            values["rmse"],
            values["mae"],
            values["mse"],
            values["nasa_score"],
            values["r2"],
        )
    return {
        "dataset": dataset,
        "seed": seed,
        "metrics": scores,
        "output_dir": output_dir,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse supported dataset, seed, config, device and epoch options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=(*DATASET_IDS, "all"), default="FD001")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument(
        "--epochs", type=int, help="Override max_epochs for smoke/debug runs"
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help="Run a small validation-only sweep before final fit",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Train requested dataset and seed combinations."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    args = parse_args(argv)
    config = load_config(args.config)
    if args.epochs is not None:
        if args.epochs <= 0:
            raise ValueError("--epochs must be positive")
        config["max_epochs"] = args.epochs
    seeds = args.seeds if args.seeds else [args.seed]
    datasets = DATASET_IDS if args.dataset == "all" else (args.dataset,)
    if args.tune and (args.dataset == "all" or len(seeds) != 1):
        raise ValueError(
            "--tune requires one dataset and seed; keep the selected config explicit"
        )
    for dataset in datasets:
        for seed in seeds:
            run_config = dict(config)
            if args.tune:
                run_config, selected_trial = tune_on_validation(
                    dataset, seed, run_config, args.device
                )
                config_path = (
                    Path(args.config)
                    if args.config is not None
                    else MODEL_DIR / "config.yaml"
                )
                config_path.write_text(
                    yaml.safe_dump(run_config, sort_keys=False), encoding="utf-8"
                )
                LOG.info(
                    "Saved selected validation config from trial=%s to %s",
                    selected_trial,
                    config_path,
                )
            train_one(dataset, seed, run_config, args.device)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
