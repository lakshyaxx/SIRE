"""Train the healthy sequence autoencoder and health-informed CMAPSS RUL head."""

from __future__ import annotations

import argparse
import copy
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

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import yaml
from torch import nn
from torch.utils.data import TensorDataset

from common.config import DATASET_IDS, cmapss_root, get_dataset_spec
from common.data import CMapssData, load_cmapss_dataset
from common.evaluate import evaluate_predictions
from common.plots import plot_loss_curve, plot_prediction_diagnostics
from common.preprocess import CMapssPreprocessor
from common.report import record_results
from common.splits import EngineSplit, get_or_create_split, split_to_dict
from common.train_utils import EarlyStopping, make_data_loader, seed_everything, select_device
from common.windows import WindowDataset, WindowSet, make_test_last_windows, make_windows

_MODEL_SPEC = importlib.util.spec_from_file_location(
    "sire_cmapss_06_autoencoder_model", MODEL_DIR / "model.py"
)
if _MODEL_SPEC is None or _MODEL_SPEC.loader is None:
    raise ImportError("Cannot load autoencoder model definition")
_MODEL_MODULE = importlib.util.module_from_spec(_MODEL_SPEC)
sys.modules[_MODEL_SPEC.name] = _MODEL_MODULE
_MODEL_SPEC.loader.exec_module(_MODEL_MODULE)
SequenceAutoencoder = _MODEL_MODULE.SequenceAutoencoder
HealthRULModel = _MODEL_MODULE.HealthRULModel
build_autoencoder = _MODEL_MODULE.build_autoencoder

_HEALTH_SPEC = importlib.util.spec_from_file_location(
    "sire_cmapss_06_autoencoder_health", MODEL_DIR / "health.py"
)
if _HEALTH_SPEC is None or _HEALTH_SPEC.loader is None:
    raise ImportError("Cannot load autoencoder health functions")
_HEALTH_MODULE = importlib.util.module_from_spec(_HEALTH_SPEC)
sys.modules[_HEALTH_SPEC.name] = _HEALTH_MODULE
_HEALTH_SPEC.loader.exec_module(_HEALTH_MODULE)
calibrate_health = _HEALTH_MODULE.calibrate_health
detect_onset = _HEALTH_MODULE.detect_onset
prognostic_quality = _HEALTH_MODULE.prognostic_quality

LOG = logging.getLogger("autoencoder_train")


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load autoencoder settings from the default or supplied YAML file."""
    config_path = Path(path) if path is not None else MODEL_DIR / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"Configuration at {config_path} must be a YAML mapping")
    return config


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically after creating the output directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _stable_hash(data: dict[str, Any]) -> str:
    """Hash a configuration mapping using a stable JSON representation."""
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _prepare(dataset: str, config: dict[str, Any]) -> dict[str, Any]:
    """Load data and prepare identical engine splits, preprocessing and windows."""
    source: CMapssData = load_cmapss_dataset(dataset, rul_cap=int(config["rul_cap"]))
    split = get_or_create_split(
        dataset,
        source.train.unit.astype(int).unique().tolist(),
        val_fraction=float(config["val_fraction"]),
        seed=int(config["split_seed"]),
    )
    prep = CMapssPreprocessor(dataset).fit(source.train, split.train_units)
    transformed_train = prep.transform(source.train)
    test_rows = prep.transform(source.test)
    train_rows = transformed_train[transformed_train.unit.isin(split.train_units)]
    val_rows = transformed_train[transformed_train.unit.isin(split.val_units)]
    columns = prep.feature_columns
    length = int(config["window_length"])
    stride = int(config["stride"])
    train_windows = make_windows(train_rows, columns, length, stride)
    val_windows = make_windows(val_rows, columns, length, stride)
    test_last = make_test_last_windows(test_rows, columns, length)
    truth = source.test_truth.set_index("unit").loc[test_last.units]
    all_test = test_rows.copy()
    max_cycles = all_test.groupby("unit").cycle.transform("max")
    truth_map = source.test_truth.set_index("unit").rul_raw
    all_test["rul_raw"] = all_test.unit.map(truth_map).astype(float) + max_cycles - all_test.cycle
    test_windows = make_windows(all_test, columns, length, stride, target_column="rul_raw")
    artifact_dir = cmapss_root() / "results" / "artifacts" / dataset
    prep.save(artifact_dir / "preprocessor.joblib")
    (artifact_dir / "split_ids.json").write_text(
        json.dumps(split_to_dict(split), indent=2) + "\n", encoding="utf-8"
    )
    LOG.info(
        "Prepared %s: train %d engines/%d windows; val %d engines/%d windows; "
        "test %d engines/%d windows (%d padded test engines); %d channels",
        dataset, len(split.train_units), len(train_windows), len(split.val_units),
        len(val_windows), len(test_last), len(test_windows), test_last.padded_engines,
        len(columns),
    )
    return {
        "source": source, "split": split, "preprocessor": prep,
        "train": train_windows, "val": val_windows, "test_last": test_last,
        "test_all": test_windows, "test_raw": truth.rul_raw.to_numpy(dtype=float),
        "test_clipped": truth.rul_clipped.to_numpy(dtype=float),
    }


def _healthy_mask(windows: WindowSet, cap: int) -> np.ndarray:
    """Select windows whose raw RUL is in the capped healthy portion."""
    if windows.y_raw is None:
        raise ValueError("Healthy-window selection requires raw RUL labels")
    return windows.y_raw >= cap


def _reconstruction_errors(
    model: SequenceAutoencoder, x: np.ndarray, device: torch.device, batch_size: int
) -> np.ndarray:
    """Return per-window, per-channel mean squared reconstruction errors."""
    model.eval()
    results: list[np.ndarray] = []
    with torch.inference_mode():
        for start in range(0, len(x), batch_size):
            values = torch.as_tensor(x[start : start + batch_size], device=device)
            _, reconstructed = model(values)
            results.append((reconstructed - values).square().mean(dim=1).cpu().numpy())
    return np.concatenate(results).astype(np.float64, copy=False)


def _fit_autoencoder(
    model: SequenceAutoencoder, train_x: np.ndarray, val_x: np.ndarray,
    output: Path, config: dict[str, Any], seed: int, device: torch.device,
) -> pd.DataFrame:
    """Train stage 1 only on healthy windows and stop on healthy-val MSE."""
    batch = int(config["batch_size"])
    train_loader = make_data_loader(
        TensorDataset(torch.from_numpy(train_x)), batch, True,
        int(config["num_workers"]), seed, device,
    )
    val_loader = make_data_loader(
        TensorDataset(torch.from_numpy(val_x)), batch, False,
        int(config["num_workers"]), seed, device,
    )
    model.to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=float(config["learning_rate"]),
        weight_decay=float(config["weight_decay"]),
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=float(config["scheduler_factor"]),
        patience=int(config["scheduler_patience"]),
    )
    stop = EarlyStopping(patience=int(config["early_stopping_patience"]))
    best: dict[str, torch.Tensor] | None = None
    history: list[dict[str, float | int | str]] = []
    for epoch in range(1, int(config["max_epochs"]) + 1):
        started = time.perf_counter()
        model.train()
        losses: list[float] = []
        for (values,) in train_loader:
            values = values.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            _, reconstruction = model(values)
            loss = nn.functional.mse_loss(reconstruction, values)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), float(config["gradient_clip"]))
            optimizer.step()
            losses.append(float(loss.detach().item()))
        model.eval()
        validation: list[float] = []
        with torch.inference_mode():
            for (values,) in val_loader:
                values = values.to(device, non_blocking=True)
                _, reconstructed = model(values)
                validation.append(float(nn.functional.mse_loss(reconstructed, values).item()))
        val_loss = float(np.mean(validation))
        scheduler.step(val_loss)
        if val_loss < stop.best:
            best = copy.deepcopy(model.state_dict())
            torch.save(best, output / "best_autoencoder.pt")
        should_stop = stop.update(val_loss, epoch)
        history.append({
            "stage": "healthy_reconstruction", "epoch": epoch,
            "train_loss": float(np.mean(losses)), "val_loss": val_loss,
            "val_rmse": float("nan"), "lr": float(optimizer.param_groups[0]["lr"]),
            "seconds": time.perf_counter() - started,
        })
        LOG.info("reconstruction epoch=%d train_mse=%.6f val_mse=%.6f", epoch, np.mean(losses), val_loss)
        if should_stop:
            LOG.info("Autoencoder early stop at epoch %d; best=%d val_mse=%.6f", epoch, stop.best_epoch, stop.best)
            break
    if best is None:
        raise RuntimeError("Healthy autoencoder stage did not produce a checkpoint")
    model.load_state_dict(best)
    return pd.DataFrame(history)


def _predict_rul(
    model: HealthRULModel, windows: WindowSet, device: torch.device, batch_size: int,
    error_mean: np.ndarray, error_std: np.ndarray, hi_mean: float, hi_std: float,
    cap: float, with_details: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]:
    """Predict cycles and optionally return HI, sensor drift and latent vectors."""
    model.eval()
    predictions: list[np.ndarray] = []
    his: list[np.ndarray] = []
    drifts: list[np.ndarray] = []
    latents: list[np.ndarray] = []
    mean_tensor = torch.as_tensor(error_mean, dtype=torch.float32, device=device)
    std_tensor = torch.as_tensor(error_std, dtype=torch.float32, device=device)
    with torch.inference_mode():
        for start in range(0, len(windows), batch_size):
            values = torch.as_tensor(windows.x[start : start + batch_size], device=device)
            prediction, latent, drift, hi = model(
                values, mean_tensor, std_tensor, hi_mean, hi_std
            )
            predictions.append((prediction.reshape(-1) * cap).cpu().numpy())
            his.append(hi.reshape(-1).cpu().numpy())
            drifts.append(drift.cpu().numpy())
            if with_details:
                latents.append(latent.cpu().numpy())
    return (
        np.concatenate(predictions), np.concatenate(his), np.concatenate(drifts),
        np.concatenate(latents) if with_details else None,
    )


def _fit_head_stage(
    model: HealthRULModel, train: WindowSet, val: WindowSet,
    output: Path, config: dict[str, Any], device: torch.device,
    error_mean: np.ndarray, error_std: np.ndarray, hi_mean: float, hi_std: float,
    learning_rate: float, max_epochs: int, patience: int, stage: str,
) -> tuple[pd.DataFrame, dict[str, torch.Tensor]]:
    """Fit the RUL head, with optional end-to-end fine tuning and best restore."""
    batch = int(config["batch_size"])
    train_loader = make_data_loader(
        WindowDataset(train), batch, True, int(config["num_workers"]),
        int(config["seed"]), device,
    )
    val_loader = make_data_loader(
        WindowDataset(val), batch, False, int(config["num_workers"]),
        int(config["seed"]), device,
    )
    if stage == "frozen_head":
        for parameter in model.autoencoder.parameters():
            parameter.requires_grad_(False)
    else:
        for parameter in model.autoencoder.parameters():
            parameter.requires_grad_(True)
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=learning_rate,
        weight_decay=float(config["weight_decay"]),
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=float(config["scheduler_factor"]),
        patience=int(config["scheduler_patience"]),
    )
    stop = EarlyStopping(patience=patience)
    best: dict[str, torch.Tensor] | None = None
    rows: list[dict[str, float | int | str]] = []
    mean_tensor = torch.as_tensor(error_mean, dtype=torch.float32, device=device)
    std_tensor = torch.as_tensor(error_std, dtype=torch.float32, device=device)
    cap = float(config["rul_cap"])
    for epoch in range(1, max_epochs + 1):
        started = time.perf_counter()
        model.train()
        losses: list[float] = []
        for values, target in train_loader:
            values = values.to(device, non_blocking=True)
            target = target.to(device, non_blocking=True).reshape(-1, 1) / cap
            optimizer.zero_grad(set_to_none=True)
            prediction, _, _, _ = model(values, mean_tensor, std_tensor, hi_mean, hi_std)
            loss = nn.functional.mse_loss(prediction, target)
            loss.backward()
            nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], float(config["gradient_clip"]))
            optimizer.step()
            losses.append(float(loss.detach().item()))
        model.eval()
        val_losses: list[float] = []
        truths: list[np.ndarray] = []
        preds: list[np.ndarray] = []
        with torch.inference_mode():
            for values, target in val_loader:
                values = values.to(device, non_blocking=True)
                target = target.to(device, non_blocking=True).reshape(-1, 1)
                prediction, _, _, _ = model(values, mean_tensor, std_tensor, hi_mean, hi_std)
                val_losses.append(float(nn.functional.mse_loss(prediction, target / cap).item()))
                truths.append(target.cpu().numpy().reshape(-1))
                preds.append((prediction.reshape(-1) * cap).cpu().numpy())
        val_rmse = float(np.sqrt(np.mean(np.square(np.concatenate(preds) - np.concatenate(truths)))))
        val_loss = float(np.mean(val_losses))
        scheduler.step(val_rmse)
        if val_rmse < stop.best:
            best = copy.deepcopy(model.state_dict())
        should_stop = stop.update(val_rmse, epoch)
        rows.append({
            "stage": stage, "epoch": epoch, "train_loss": float(np.mean(losses)),
            "val_loss": val_loss, "val_rmse": val_rmse,
            "lr": float(optimizer.param_groups[0]["lr"]),
            "seconds": time.perf_counter() - started,
        })
        LOG.info("%s epoch=%d train_mse=%.6f val_rmse=%.4f", stage, epoch, np.mean(losses), val_rmse)
        if should_stop:
            break
    if best is None:
        raise RuntimeError(f"{stage} stage did not produce a best checkpoint")
    model.load_state_dict(best)
    return pd.DataFrame(rows), best


def _health_frame(
    windows: WindowSet, hi: np.ndarray, drift: np.ndarray,
    channel_errors: np.ndarray, channels: list[str],
    hi_threshold: float, consecutive: int, failure_cycle: dict[int, float] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Create per-window HI/drift/onset tables and aggregate onset/quality metrics."""
    frame = pd.DataFrame({"unit": windows.units, "step": windows.steps, "hi": hi})
    if windows.y_raw is not None:
        frame["rul_raw"] = windows.y_raw
    elif windows.y is not None:
        frame["rul_raw"] = windows.y
    else:
        frame["rul_raw"] = np.nan
    drift_frame = pd.DataFrame(drift, columns=channels)
    error_frame = pd.DataFrame(channel_errors, columns=channels)
    id_columns = frame[["unit", "step", "hi", "rul_raw"]]
    z_long = pd.concat([id_columns, drift_frame], axis=1).melt(
        id_vars=["unit", "step", "hi", "rul_raw"], value_vars=channels,
        var_name="channel", value_name="z",
    )
    errors_long = pd.concat([id_columns, error_frame], axis=1).melt(
        id_vars=["unit", "step", "hi", "rul_raw"], value_vars=channels,
        var_name="channel", value_name="error",
    )
    long = z_long.merge(errors_long, on=["unit", "step", "hi", "rul_raw", "channel"])
    records: list[dict[str, Any]] = []
    for unit, group in frame.groupby("unit", sort=True):
        group = group.sort_values("step", kind="stable")
        onset = detect_onset(
            group.step.to_numpy(), group.hi.to_numpy(), hi_threshold, consecutive
        )
        failure = failure_cycle.get(int(unit)) if failure_cycle is not None else None
        records.append({
            "unit": int(unit), "onset_step": onset,
            "failure_cycle": failure,
            "lead_time_cycles": float(failure - onset) if failure is not None and onset is not None else np.nan,
        })
    onset_frame = pd.DataFrame(records)
    quality = prognostic_quality(frame.dropna(subset=["rul_raw"])) if frame.rul_raw.notna().any() else {}
    detected = onset_frame.onset_step.notna()
    onset_metrics = {
        "onset_threshold_hi": float(hi_threshold),
        "onset_consecutive_steps": int(consecutive),
        "units_with_onset": int(detected.sum()),
        "onset_share": float(detected.mean()) if len(detected) else 0.0,
        "median_lead_time_cycles": float(onset_frame.loc[detected, "lead_time_cycles"].median())
        if (detected & onset_frame.lead_time_cycles.notna()).any() else None,
    }
    return long, onset_frame, {"quality": quality, **onset_metrics}


def _write_health_figures(
    health: pd.DataFrame, onset: pd.DataFrame, channels: list[str], figures: Path,
    threshold: float,
) -> None:
    """Save HI/onset plots for six engines and channel-drift heatmaps for three."""
    figures.mkdir(parents=True, exist_ok=True)
    selected = sorted(health.unit.unique())[:6]
    fig, axes = plt.subplots(len(selected), 1, figsize=(11, max(3, 2.2 * len(selected))), squeeze=False)
    onsets = onset.set_index("unit").onset_step.to_dict()
    for axis, unit in zip(axes[:, 0], selected):
        group = health[health.unit == unit].drop_duplicates("step").sort_values("step")
        axis.plot(group.step, group.hi, linewidth=1.1)
        axis.axhline(threshold, color="tab:red", linestyle="--", linewidth=0.8)
        onset_step = onsets.get(unit)
        if onset_step is not None and not pd.isna(onset_step):
            axis.axvline(onset_step, color="tab:orange", linestyle=":", linewidth=1.1)
        axis.set_ylabel(f"Unit {unit}\nHI")
    axes[-1, 0].set_xlabel("Cycle")
    fig.tight_layout()
    fig.savefig(figures / "hi_test_units.png", dpi=150)
    plt.close(fig)
    for unit in sorted(health.unit.unique())[:3]:
        group = health[health.unit == unit].sort_values("step")
        matrix = group.pivot(index="channel", columns="step", values="z").reindex(channels).to_numpy(dtype=float)
        fig, axis = plt.subplots(figsize=(11, 5))
        image = axis.imshow(matrix, aspect="auto", interpolation="nearest", cmap="coolwarm")
        axis.set_yticks(np.arange(len(channels)), labels=channels)
        axis.set_xlabel("Observed window endpoint index (cycles ordered)")
        axis.set_ylabel("Sensor / setting channel")
        axis.set_title(f"Unit {unit}: calibrated reconstruction-error z-scores")
        fig.colorbar(image, ax=axis, label="z-score")
        fig.tight_layout()
        fig.savefig(figures / f"sensor_drift_unit_{unit}.png", dpi=150)
        plt.close(fig)


def train_one(
    dataset: str, seed: int, config: dict[str, Any], device_request: str = "auto"
) -> dict[str, Any]:
    """Run both stages, evaluate the model, save health outputs, and refresh report."""
    dataset = get_dataset_spec(dataset).dataset
    run = dict(config)
    run.update({"dataset": dataset, "seed": int(seed), "model": "06_autoencoder"})
    data = _prepare(dataset, run)
    train_windows: WindowSet = data["train"]
    val_windows: WindowSet = data["val"]
    cap = int(run["healthy_rul_min"])
    train_healthy = _healthy_mask(train_windows, cap)
    val_healthy = _healthy_mask(val_windows, cap)
    if train_healthy.sum() < 2 or val_healthy.sum() < 2:
        raise ValueError("Need at least two healthy train and validation windows for autoencoder calibration")
    LOG.info("Healthy selection: raw RUL >= %d; train=%d val=%d windows", cap, train_healthy.sum(), val_healthy.sum())
    seed_everything(seed)
    device = select_device(device_request)
    channels = list(data["preprocessor"].feature_columns)
    output = MODEL_DIR / "outputs" / dataset / f"seed_{seed}"
    output.mkdir(parents=True, exist_ok=True)
    autoencoder = build_autoencoder(len(channels), run)
    started = time.perf_counter()
    recon_history = _fit_autoencoder(
        autoencoder, train_windows.x[train_healthy], val_windows.x[val_healthy],
        output, run, seed, device,
    )
    val_healthy_errors = _reconstruction_errors(
        autoencoder, val_windows.x[val_healthy], device, int(run["batch_size"])
    )
    error_mean, error_std, healthy_hi_mean, healthy_hi_std = calibrate_health(val_healthy_errors)
    LOG.info("Calibrated HI using %d healthy validation windows", int(val_healthy.sum()))

    model = HealthRULModel(autoencoder, int(run["rul_head_hidden_size"])).to(device)
    frozen_history, best_head_state = _fit_head_stage(
        model, train_windows, val_windows, output, run, device,
        error_mean, error_std, healthy_hi_mean, healthy_hi_std,
        float(run["learning_rate"]), int(run["rul_head_epochs"]),
        int(run["rul_head_patience"]), "frozen_head",
    )
    fine_history, best_finetune_state = _fit_head_stage(
        model, train_windows, val_windows, output, run, device,
        error_mean, error_std, healthy_hi_mean, healthy_hi_std,
        float(run["finetune_learning_rate"]), int(run["finetune_epochs"]),
        max(10, int(run["finetune_epochs"])), "finetune",
    )
    combined_history = pd.concat([recon_history, frozen_history, fine_history], ignore_index=True)
    head_stage_best = float(frozen_history.val_rmse.min())
    fine_stage_best = float(fine_history.val_rmse.min())
    if fine_stage_best < head_stage_best:
        model.load_state_dict(best_finetune_state)
        best_stage = "finetune"
        best_epoch = int(fine_history.loc[fine_history.val_rmse.idxmin(), "epoch"])
    else:
        model.load_state_dict(best_head_state)
        best_stage = "frozen_head"
        best_epoch = int(frozen_history.loc[frozen_history.val_rmse.idxmin(), "epoch"])
    combined_history.to_csv(output / "history.csv", index=False)
    training_seconds = time.perf_counter() - started

    pred_val, hi_val, drift_val, _ = _predict_rul(
        model, val_windows, device, int(run["batch_size"]), error_mean, error_std,
        healthy_hi_mean, healthy_hi_std, float(run["rul_cap"]),
    )
    pred_test, hi_test_last, drift_test_last, _ = _predict_rul(
        model, data["test_last"], device, int(run["batch_size"]), error_mean,
        error_std, healthy_hi_mean, healthy_hi_std, float(run["rul_cap"]),
    )
    scores = evaluate_predictions(
        val_windows.y, pred_val, data["test_raw"], pred_test,
        rul_cap=float(run["rul_cap"]),
    )
    pred_test_all, hi_test_all, drift_test_all, _ = _predict_rul(
        model, data["test_all"], device, int(run["batch_size"]), error_mean,
        error_std, healthy_hi_mean, healthy_hi_std, float(run["rul_cap"]),
    )
    del pred_test_all
    test_rows = data["source"].test
    max_cycle_by_unit = test_rows.groupby("unit").cycle.max()
    failure_cycle = {
        int(unit): float(max_cycle_by_unit.loc[unit] + rul)
        for unit, rul in zip(data["source"].test_truth.unit, data["test_raw"])
    }
    test_errors = _reconstruction_errors(
        model.autoencoder, data["test_all"].x, device, int(run["batch_size"])
    )
    onset_threshold = healthy_hi_mean + float(run["onset_z_threshold"]) * healthy_hi_std
    hi_frame, onset_frame, health_metrics = _health_frame(
        data["test_all"], hi_test_all, drift_test_all, test_errors, channels,
        onset_threshold,
        int(run["onset_consecutive_steps"]), failure_cycle,
    )
    # Separate test and validation prognostic quality summaries use only each split's labels.
    val_health = pd.DataFrame({
        "unit": val_windows.units, "step": val_windows.steps, "hi": hi_val,
        "rul_raw": val_windows.y_raw,
    })
    health_metrics["validation_quality"] = prognostic_quality(val_health)
    hi_frame[["unit", "step", "hi", "rul_raw"]].drop_duplicates(
        ["unit", "step"]
    ).to_csv(output / "hi_test.csv", index=False)
    onset_frame.to_csv(output / "onset.csv", index=False)
    hi_frame.to_csv(output / "reconstruction_errors_test.csv", index=False)
    health_metrics["test_onset"] = {
        key: health_metrics.pop(key) for key in (
            "onset_threshold_hi", "onset_consecutive_steps", "units_with_onset",
            "onset_share", "median_lead_time_cycles",
        )
    }
    _write_json(output / "health_metrics.json", health_metrics)
    _write_health_figures(
        hi_frame, onset_frame, channels, output / "figures", onset_threshold
    )

    config_used = dict(run)
    config_used.update({
        "device": str(device), "n_features": len(channels),
        "feature_columns": channels,
        "dropped_constant_sensors": list(data["preprocessor"].dropped_sensors),
        "train_engines": len(data["split"].train_units),
        "validation_engines": len(data["split"].val_units),
        "train_windows": len(train_windows), "validation_windows": len(val_windows),
        "healthy_train_windows": int(train_healthy.sum()),
        "healthy_validation_windows": int(val_healthy.sum()),
        "healthy_window_rule": f"raw training RUL >= {cap} cycles",
        "padded_test_engines": data["test_last"].padded_engines,
        "healthy_error_mean": error_mean.tolist(), "healthy_error_std": error_std.tolist(),
        "healthy_hi_mean": healthy_hi_mean, "healthy_hi_std": healthy_hi_std,
        "selected_rul_stage": best_stage,
    })
    (output / "config_used.yaml").write_text(yaml.safe_dump(config_used, sort_keys=False), encoding="utf-8")
    torch.save({name: tensor.detach().cpu() for name, tensor in model.state_dict().items()}, output / "best_model.pt")

    def prediction_frame(windows: WindowSet, prediction: np.ndarray, raw: np.ndarray, clipped: np.ndarray, split_name: str) -> pd.DataFrame:
        """Build the shared prediction output schema."""
        return pd.DataFrame({
            "unit": windows.units, "step": windows.steps,
            "y_true_raw": raw, "y_true_clipped": clipped,
            "y_pred": prediction, "error": prediction - raw, "split": split_name,
        })

    val_raw = val_windows.y_raw if val_windows.y_raw is not None else val_windows.y
    prediction_frame(val_windows, pred_val, val_raw, val_windows.y, "val").to_csv(output / "predictions_val.csv", index=False)
    prediction_frame(data["test_last"], pred_test, data["test_raw"], data["test_clipped"], "test").to_csv(output / "predictions_test.csv", index=False)
    plot_loss_curve(combined_history[combined_history.stage != "healthy_reconstruction"], output / "figures" / "loss_curve.png")
    plot_prediction_diagnostics(val_windows.y, pred_val, output / "figures" / "validation", val_windows.units)
    plot_prediction_diagnostics(data["test_raw"], pred_test, output / "figures" / "test_raw", data["test_last"].units)
    plot_prediction_diagnostics(data["test_clipped"], pred_test, output / "figures" / "test_clipped", data["test_last"].units)
    recon_history.to_csv(output / "reconstruction_history.csv", index=False)

    n_params = sum(parameter.numel() for parameter in model.parameters())
    config_hash = _stable_hash(config_used)
    metrics_payload = {
        "dataset": dataset, "model": "06_autoencoder", "seed": seed,
        "device": str(device), "metrics": scores, "health_metrics": health_metrics,
        "n_params": n_params, "train_seconds": training_seconds,
        "selected_rul_stage": best_stage, "best_rul_epoch": best_epoch,
        "reconstruction_epochs": len(recon_history),
        "frozen_head_epochs": len(frozen_history), "finetune_epochs": len(fine_history),
        "padded_test_engines": data["test_last"].padded_engines,
        "dropped_constant_sensors": list(data["preprocessor"].dropped_sensors),
        "config_hash": config_hash,
    }
    _write_json(output / "metrics.json", metrics_payload)
    timestamp = datetime.now(timezone.utc).isoformat()
    metric_rows = (
        ("val", "window", "clipped", scores["val"]),
        ("test", "engine", "raw", scores["test_raw"]),
        ("test", "engine", "clipped", scores["test_clipped"]),
    )
    record_results([
        {
            "track": "CMAPSS", "dataset": dataset, "model": "06_autoencoder",
            "seed": seed, "split": split, "level": level, "target_type": target,
            **values, "n_params": n_params, "train_seconds": training_seconds,
            "device": str(device), "config_hash": config_hash, "timestamp": timestamp,
        }
        for split, level, target, values in metric_rows
    ])
    LOG.info("Selected RUL stage=%s epoch=%d; train_seconds=%.2f", best_stage, best_epoch, training_seconds)
    for split_name, values in scores.items():
        LOG.info("%s RMSE=%.4f MAE=%.4f MSE=%.4f NASA=%.4f R2=%.4f", split_name, values["rmse"], values["mae"], values["mse"], values["nasa_score"], values["r2"])
    LOG.info("Test onset share=%.3f; median lead time=%s cycles", health_metrics["test_onset"]["onset_share"], health_metrics["test_onset"]["median_lead_time_cycles"])
    return metrics_payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse dataset, seed, configuration, device, and epoch override options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=(*DATASET_IDS, "all"), default="FD001")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--epochs", type=int, help="Override stage-1 max_epochs for smoke/debug runs")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Train requested dataset and seed combinations."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    config = load_config(args.config)
    if args.epochs is not None:
        if args.epochs <= 0:
            raise ValueError("--epochs must be positive")
        config["max_epochs"] = args.epochs
        config["rul_head_epochs"] = min(int(config["rul_head_epochs"]), args.epochs)
        config["finetune_epochs"] = min(int(config["finetune_epochs"]), max(1, args.epochs))
    datasets = DATASET_IDS if args.dataset == "all" else (args.dataset,)
    seeds = args.seeds if args.seeds else [args.seed]
    for dataset in datasets:
        for seed in seeds:
            train_one(dataset, seed, config, args.device)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
