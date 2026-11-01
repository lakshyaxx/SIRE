"""Train and evaluate the C-MAPSS BiLSTM temporal-attention model."""

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

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
    "sire_cmapss_03_bilstm_attention_model", MODEL_DIR / "model.py"
)
if _MODEL_SPEC is None or _MODEL_SPEC.loader is None:
    raise ImportError("Cannot load BiLSTM attention model definition")
_MODEL_MODULE = importlib.util.module_from_spec(_MODEL_SPEC)
sys.modules[_MODEL_SPEC.name] = _MODEL_MODULE
_MODEL_SPEC.loader.exec_module(_MODEL_MODULE)
BiLSTMAttentionRegressor = _MODEL_MODULE.BiLSTMAttentionRegressor
build_model = _MODEL_MODULE.build_model

LOG = logging.getLogger("bilstm_attention_train")


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
    """Load model configuration from the default or supplied YAML file."""
    config_path = Path(path) if path is not None else MODEL_DIR / "config.yaml"
    value = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Configuration at {config_path} must contain a YAML mapping")
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically after making the containing directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _config_hash(config: dict[str, Any]) -> str:
    """Hash a stable JSON representation of the effective run configuration."""
    encoded = json.dumps(
        config, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def prepare_dataset(dataset: str, config: dict[str, Any]) -> PreparedData:
    """Create shared, leakage-safe train/validation/test windows."""
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


def _predict_windows(
    model: BiLSTMAttentionRegressor,
    windows: WindowSet,
    device: torch.device,
    batch_size: int,
    seed: int,
    rul_cap: float,
    return_attention: bool = False,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Predict windows in batches, optionally collecting attention weights."""
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
    attentions: list[np.ndarray] = []
    model.eval()
    with torch.inference_mode():
        for inputs in loader:
            inputs = inputs.to(device, non_blocking=True)
            if return_attention:
                prediction, attention = model(inputs, return_attention=True)
                attentions.append(attention.cpu().numpy())
            else:
                prediction = model(inputs)
            predictions.append((prediction.reshape(-1) * rul_cap).cpu().numpy())
    if not predictions:
        raise ValueError("Cannot predict an empty window set")
    prediction_values = np.concatenate(predictions).astype(float, copy=False)
    attention_values = np.concatenate(attentions) if return_attention else None
    return prediction_values, attention_values


def _prediction_frame(
    units: np.ndarray,
    steps: np.ndarray,
    y_raw: np.ndarray,
    y_clipped: np.ndarray,
    y_pred: np.ndarray,
    split: str,
) -> pd.DataFrame:
    """Build a prediction frame matching the Phase A output contract."""
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


def _window_cycles(history: pd.DataFrame, window_length: int) -> np.ndarray:
    """Return actual cycle labels aligned with the padded final attention window."""
    cycles = history.sort_values("cycle", kind="stable")["cycle"].to_numpy(dtype=int)
    selected = cycles[-window_length:]
    if selected.size < window_length:
        selected = np.concatenate(
            [np.repeat(selected[:1], window_length - selected.size), selected]
        )
    return selected


def _save_attention_outputs(
    source: CMapssData,
    windows: WindowSet,
    attention: np.ndarray,
    output_dir: Path,
    config: dict[str, Any],
) -> int:
    """Save weights for selected test engines and plot five temporal maps."""
    n_examples = min(int(config["attention_test_units"]), len(windows.units))
    example_indices = np.argsort(windows.units, kind="stable")[:n_examples]
    examples: list[dict[str, int | float]] = []
    for index in example_indices:
        unit = int(windows.units[index])
        history = source.test.loc[source.test["unit"].eq(unit)]
        cycles = _window_cycles(history, int(config["window_length"]))
        for position, (cycle, weight) in enumerate(
            zip(cycles, attention[index], strict=True), start=1
        ):
            examples.append(
                {
                    "unit": unit,
                    "step": int(windows.steps[index]),
                    "window_position": position,
                    "cycle": int(cycle),
                    "attention_weight": float(weight),
                }
            )
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(examples).to_csv(output_dir / "attention_examples.csv", index=False)

    n_plot = min(int(config["attention_plot_units"]), n_examples)
    figure_dir = output_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(9, 5))
    positions = np.arange(1, attention.shape[1] + 1)
    for index in example_indices[:n_plot]:
        axis.plot(
            positions,
            attention[index],
            label=f"Engine {int(windows.units[index])}",
        )
    axis.set(
        xlabel="Position in final window (oldest to latest)",
        ylabel="Attention weight",
        title=f"Temporal attention for {source.dataset} test engines",
    )
    axis.legend()
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(figure_dir / "attention_examples.png", dpi=150)
    plt.close(figure)
    return n_examples


def train_one(
    dataset: str,
    seed: int,
    config: dict[str, Any],
    device_request: str = "auto",
) -> dict[str, Any]:
    """Fit one dataset/seed, save attention and prediction outputs, and report."""
    dataset = get_dataset_spec(dataset).dataset
    run_config = dict(config)
    run_config.update(
        {"dataset": dataset, "seed": int(seed), "model": "03_bilstm_attention"}
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
    val_pred, _ = _predict_windows(
        model,
        prepared.val_windows,
        device,
        int(run_config["batch_size"]),
        seed,
        float(run_config["rul_cap"]),
    )
    test_pred, test_attention = _predict_windows(
        model,
        prepared.test_windows,
        device,
        int(run_config["batch_size"]),
        seed,
        float(run_config["rul_cap"]),
        return_attention=True,
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
    if test_attention is None:
        raise RuntimeError("Test attention weights were not returned by the model")
    attention_units = _save_attention_outputs(
        prepared.source,
        prepared.test_windows,
        test_attention,
        output_dir,
        run_config,
    )

    n_params = sum(parameter.numel() for parameter in model.parameters())
    config_hash_value = _config_hash(config_used)
    best_epoch = int(history.loc[history["val_rmse"].idxmin(), "epoch"])
    metric_payload = {
        "dataset": dataset,
        "model": "03_bilstm_attention",
        "seed": seed,
        "device": str(device),
        "metrics": scores,
        "n_params": n_params,
        "train_seconds": train_seconds,
        "best_epoch": best_epoch,
        "epochs_completed": len(history),
        "padded_test_engines": prepared.test_windows.padded_engines,
        "attention_test_units": attention_units,
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
            "model": "03_bilstm_attention",
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
        "Best epoch=%d/%d; train_seconds=%.2f; parameters=%d; attention units=%d",
        best_epoch,
        len(history),
        train_seconds,
        n_params,
        attention_units,
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
    """Parse dataset, seed, config, device, and epoch options."""
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
