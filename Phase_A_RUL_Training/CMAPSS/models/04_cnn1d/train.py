"""Train and evaluate the C-MAPSS 1D-CNN RUL model."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
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
from common.data import CMapssData, load_cmapss_dataset
from common.evaluate import evaluate_predictions
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
    "sire_cmapss_04_cnn1d_model", MODEL_DIR / "model.py"
)
if _MODEL_SPEC is None or _MODEL_SPEC.loader is None:
    raise ImportError("Cannot load CNN1D model definition")
_MODEL_MODULE = importlib.util.module_from_spec(_MODEL_SPEC)
sys.modules[_MODEL_SPEC.name] = _MODEL_MODULE
_MODEL_SPEC.loader.exec_module(_MODEL_MODULE)
CNN1DRegressor = _MODEL_MODULE.CNN1DRegressor
build_model = _MODEL_MODULE.build_model

LOG = logging.getLogger("cnn1d_train")


@dataclass
class PreparedData:
    """Shared split, preprocessor, windows, and official test targets."""

    source: CMapssData
    split: EngineSplit
    preprocessor: CMapssPreprocessor
    train_windows: WindowSet
    val_windows: WindowSet
    test_windows: WindowSet
    y_test_raw: np.ndarray
    y_test_clipped: np.ndarray


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load model settings from the default or supplied YAML file."""
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
    """Hash a stable JSON representation of the effective run config."""
    encoded = json.dumps(
        config, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def prepare_dataset(dataset: str, config: dict[str, Any]) -> PreparedData:
    """Build normalized windows using the shared engine split and preprocessor."""
    spec = get_dataset_spec(dataset)
    source = load_cmapss_dataset(spec.dataset, rul_cap=int(config["rul_cap"]))
    split = get_or_create_split(
        spec.dataset,
        source.train["unit"].astype(int).unique().tolist(),
        val_fraction=float(config["val_fraction"]),
        seed=int(config["split_seed"]),
    )
    preprocessor = CMapssPreprocessor(spec.dataset).fit(
        source.train, split.train_units
    )
    transformed_train = preprocessor.transform(source.train)
    transformed_test = preprocessor.transform(source.test)
    train_rows = transformed_train.loc[
        transformed_train["unit"].isin(split.train_units)
    ]
    val_rows = transformed_train.loc[
        transformed_train["unit"].isin(split.val_units)
    ]
    window_length = int(config["window_length"])
    stride = int(config["stride"])
    train_windows = make_windows(
        train_rows,
        preprocessor.feature_columns,
        window_length=window_length,
        stride=stride,
    )
    val_windows = make_windows(
        val_rows,
        preprocessor.feature_columns,
        window_length=window_length,
        stride=stride,
    )
    test_windows = make_test_last_windows(
        transformed_test,
        preprocessor.feature_columns,
        window_length=window_length,
    )
    truth = source.test_truth.set_index("unit").loc[test_windows.units]
    artifacts_dir = cmapss_root() / "results" / "artifacts" / spec.dataset
    preprocessor.save(artifacts_dir / "preprocessor.joblib")
    (artifacts_dir / "split_ids.json").write_text(
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
    return PreparedData(
        source=source,
        split=split,
        preprocessor=preprocessor,
        train_windows=train_windows,
        val_windows=val_windows,
        test_windows=test_windows,
        y_test_raw=truth["rul_raw"].to_numpy(dtype=float),
        y_test_clipped=truth["rul_clipped"].to_numpy(dtype=float),
    )


def _predict(
    model: CNN1DRegressor,
    windows: WindowSet,
    device: torch.device,
    batch_size: int,
    seed: int,
    rul_cap: float,
) -> np.ndarray:
    """Predict windows in batches and rescale outputs to cycles."""
    inference_set = WindowSet(
        windows.x, None, windows.units, windows.steps, windows.padded_engines
    )
    loader = make_data_loader(
        WindowDataset(inference_set),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        seed=seed,
        device=device,
    )
    predictions: list[np.ndarray] = []
    model.eval()
    with torch.inference_mode():
        for inputs in loader:
            inputs = inputs.to(device, non_blocking=True)
            predictions.append(
                (model(inputs).reshape(-1) * rul_cap).cpu().numpy()
            )
    if not predictions:
        raise ValueError("Cannot predict an empty window set")
    return np.concatenate(predictions).astype(float, copy=False)


def _prediction_frame(
    units: np.ndarray,
    steps: np.ndarray,
    y_raw: np.ndarray,
    y_clipped: np.ndarray,
    y_pred: np.ndarray,
    split: str,
) -> pd.DataFrame:
    """Build the standard prediction CSV with both target variants."""
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
    """Train one dataset and seed, save artifacts, score, and update reports."""
    dataset = get_dataset_spec(dataset).dataset
    run_config = dict(config)
    run_config.update(
        {"dataset": dataset, "seed": int(seed), "model": "04_cnn1d"}
    )
    prepared = prepare_dataset(dataset, run_config)
    seed_everything(seed)
    device = select_device(device_request)
    train_loader = make_data_loader(
        WindowDataset(prepared.train_windows),
        batch_size=int(run_config["batch_size"]),
        shuffle=True,
        num_workers=int(run_config["num_workers"]),
        seed=seed,
        device=device,
    )
    val_loader = make_data_loader(
        WindowDataset(prepared.val_windows),
        batch_size=int(run_config["batch_size"]),
        shuffle=False,
        num_workers=int(run_config["num_workers"]),
        seed=seed,
        device=device,
    )
    model = build_model(len(prepared.preprocessor.feature_columns), run_config)
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
    val_pred = _predict(
        model,
        prepared.val_windows,
        device,
        int(run_config["batch_size"]),
        seed,
        float(run_config["rul_cap"]),
    )
    test_pred = _predict(
        model,
        prepared.test_windows,
        device,
        int(run_config["batch_size"]),
        seed,
        float(run_config["rul_cap"]),
    )
    scores = evaluate_predictions(
        prepared.val_windows.y,
        val_pred,
        prepared.y_test_raw,
        test_pred,
        rul_cap=float(run_config["rul_cap"]),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    config_used = dict(run_config)
    config_used.update(
        {
            "device": str(device),
            "n_features": len(prepared.preprocessor.feature_columns),
            "dropped_constant_sensors": list(prepared.preprocessor.dropped_sensors),
            "train_engines": len(prepared.split.train_units),
            "validation_engines": len(prepared.split.val_units),
            "train_windows": len(prepared.train_windows),
            "validation_windows": len(prepared.val_windows),
            "padded_test_engines": prepared.test_windows.padded_engines,
        }
    )
    (output_dir / "config_used.yaml").write_text(
        yaml.safe_dump(config_used, sort_keys=False), encoding="utf-8"
    )
    weights_path = output_dir / "best_model.pt"
    torch.save(
        {name: tensor.detach().cpu() for name, tensor in model.state_dict().items()},
        weights_path,
    )
    val_raw = (
        prepared.val_windows.y_raw
        if prepared.val_windows.y_raw is not None
        else prepared.val_windows.y
    )
    _prediction_frame(
        prepared.val_windows.units,
        prepared.val_windows.steps,
        val_raw,
        prepared.val_windows.y,
        val_pred,
        "val",
    ).to_csv(output_dir / "predictions_val.csv", index=False)
    _prediction_frame(
        prepared.test_windows.units,
        prepared.test_windows.steps,
        prepared.y_test_raw,
        prepared.y_test_clipped,
        test_pred,
        "test",
    ).to_csv(output_dir / "predictions_test.csv", index=False)
    plot_loss_curve(history, figures_dir / "loss_curve.png")
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
    plot_prediction_diagnostics(
        prepared.y_test_clipped,
        test_pred,
        figures_dir / "test_clipped",
        prepared.test_windows.units,
    )

    n_params = sum(parameter.numel() for parameter in model.parameters())
    config_hash_value = _config_hash(config_used)
    best_epoch = int(history.loc[history["val_rmse"].idxmin(), "epoch"])
    metric_payload = {
        "dataset": dataset,
        "model": "04_cnn1d",
        "seed": seed,
        "device": str(device),
        "metrics": scores,
        "n_params": n_params,
        "train_seconds": train_seconds,
        "best_epoch": best_epoch,
        "epochs_completed": len(history),
        "padded_test_engines": prepared.test_windows.padded_engines,
        "dropped_constant_sensors": list(prepared.preprocessor.dropped_sensors),
        "config_hash": config_hash_value,
    }
    _write_json(output_dir / "metrics.json", metric_payload)
    timestamp = datetime.now(timezone.utc).isoformat()
    metric_rows = (
        ("val", "window", "clipped", scores["val"]),
        ("test", "engine", "raw", scores["test_raw"]),
        ("test", "engine", "clipped", scores["test_clipped"]),
    )
    result_rows = [
        {
            "track": "CMAPSS",
            "dataset": dataset,
            "model": "04_cnn1d",
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
        for split_name, level, target_type, values in metric_rows
    ]
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
    return {"dataset": dataset, "seed": seed, "metrics": scores}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse supported dataset, seed, config, device, and epoch options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=(*DATASET_IDS, "all"), default="FD001")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument(
        "--epochs", type=int, help="Override max_epochs for smoke/debug runs"
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
    for dataset in datasets:
        for seed in seeds:
            run_config = dict(config)
            run_config["seed"] = seed
            train_one(dataset, seed, run_config, args.device)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
