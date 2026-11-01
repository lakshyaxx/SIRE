"""Load the trained health autoencoder and predict from raw engine histories."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

MODEL_DIR = Path(__file__).resolve().parent
TRACK_ROOT = MODEL_DIR.parents[1]
for import_path in (TRACK_ROOT, MODEL_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import numpy as np
import pandas as pd
import torch
import yaml

from common.config import cmapss_root
from common.predictor_base import PredictorBase
from common.preprocess import CMapssPreprocessor, load_preprocessor

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

_HEALTH_SPEC = importlib.util.spec_from_file_location(
    "sire_cmapss_06_autoencoder_health", MODEL_DIR / "health.py"
)
if _HEALTH_SPEC is None or _HEALTH_SPEC.loader is None:
    raise ImportError("Cannot load autoencoder health functions")
_HEALTH_MODULE = importlib.util.module_from_spec(_HEALTH_SPEC)
sys.modules[_HEALTH_SPEC.name] = _HEALTH_MODULE
_HEALTH_SPEC.loader.exec_module(_HEALTH_MODULE)
detect_onset = _HEALTH_MODULE.detect_onset


class AutoencoderPredictor(PredictorBase):
    """Predict RUL and expose calibrated HI, sensor drift, and onset from raw rows."""

    def __init__(
        self, model: Any, preprocessor: CMapssPreprocessor, dataset: str,
        seed: int, version: str, config: dict[str, Any], device: torch.device,
    ) -> None:
        """Initialize the common history interface and saved calibration state."""
        super().__init__(
            preprocessor, "06_autoencoder", dataset, seed, version,
            int(config["window_length"]),
        )
        self.network = model
        self.device = device
        self.rul_cap = float(config["rul_cap"])
        self.error_mean = torch.as_tensor(config["healthy_error_mean"], dtype=torch.float32, device=device)
        self.error_std = torch.as_tensor(config["healthy_error_std"], dtype=torch.float32, device=device)
        self.hi_mean = float(config["healthy_hi_mean"])
        self.hi_std = float(config["healthy_hi_std"])
        self.onset_threshold = self.hi_mean + float(config["onset_z_threshold"]) * self.hi_std
        self.onset_steps = int(config["onset_consecutive_steps"])

    def predict_window(self, window: np.ndarray) -> tuple[float, dict[str, Any]]:
        """Return the latest RUL and calibrated health diagnostics for one window."""
        tensor = torch.as_tensor(window, dtype=torch.float32, device=self.device)
        self.network.eval()
        with torch.inference_mode():
            prediction, _, drift, hi = self.network(
                tensor, self.error_mean, self.error_std, self.hi_mean, self.hi_std
            )
        drift_values = drift[0].cpu().numpy()
        details = {
            "hi": float(hi.reshape(-1)[0].item()),
            "sensor_drift": {
                name: float(value)
                for name, value in zip(self.preprocessor.feature_columns, drift_values)
            },
        }
        return float(prediction.reshape(-1)[0].item() * self.rul_cap), details

    def predict_rul(self, history: pd.DataFrame) -> dict[str, Any]:
        """Predict RUL and find onset from the full available history, using causal windows."""
        latest_window, used, warnings = self.prepare_window(history)
        prediction, details = self.predict_window(latest_window)
        raw = history.copy()
        if "unit" not in raw:
            raw["unit"] = 1
        raw = raw.sort_values("cycle", kind="stable")
        transformed = self.preprocessor.transform(raw)
        channels = transformed[list(self.preprocessor.feature_columns)].to_numpy(dtype=np.float32)
        windows = []
        steps = transformed.cycle.to_numpy(dtype=np.int64)
        for end in range(len(channels)):
            start = max(0, end - self.window_length + 1)
            window = channels[start : end + 1]
            if len(window) < self.window_length:
                pad = np.repeat(window[:1], self.window_length - len(window), axis=0)
                window = np.concatenate((pad, window), axis=0)
            windows.append(window)
        values = torch.as_tensor(np.stack(windows), dtype=torch.float32, device=self.device)
        his: list[np.ndarray] = []
        with torch.inference_mode():
            for batch in values.split(256):
                _, _, _, hi = self.network(
                    batch, self.error_mean, self.error_std, self.hi_mean, self.hi_std
                )
                his.append(hi.reshape(-1).cpu().numpy())
        hi_values = np.concatenate(his)
        details["onset_step"] = detect_onset(
            steps, hi_values, self.onset_threshold, self.onset_steps
        )
        return {
            "rul": prediction,
            "rul_unit": "cycles",
            "n_steps_used": int(used),
            "model": self.model,
            "dataset": self.dataset,
            "seed": self.seed,
            "version": self.version,
            "warnings": warnings,
            **details,
        }


def load_model(dataset: str, seed: int | None = None) -> AutoencoderPredictor:
    """Load weights, preprocessor, and healthy-validation calibration artifacts."""
    normalized = dataset.upper()
    selected_seed = int(seed if seed is not None else 42)
    output = MODEL_DIR / "outputs" / normalized / f"seed_{selected_seed}"
    model_path = output / "best_model.pt"
    config_path = output / "config_used.yaml"
    preprocessor_path = cmapss_root() / "results" / "artifacts" / normalized / "preprocessor.joblib"
    missing = [path for path in (model_path, config_path, preprocessor_path) if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing trained predictor artifacts: " + ", ".join(map(str, missing)))
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    preprocessor = load_preprocessor(preprocessor_path)
    if preprocessor.dataset != normalized:
        raise ValueError(f"Preprocessor dataset {preprocessor.dataset} does not match {normalized}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    autoencoder = SequenceAutoencoder(
        input_size=len(preprocessor.feature_columns),
        hidden_size=int(config["encoder_hidden_size"]),
        num_layers=int(config["encoder_layers"]),
        latent_size=int(config["latent_size"]),
        decoder_hidden_size=int(config["decoder_hidden_size"]),
        dropout=float(config["dropout"]),
    )
    model = HealthRULModel(autoencoder, int(config["rul_head_hidden_size"]))
    model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
    model.to(device).eval()
    version = hashlib.sha256(config_path.read_bytes() + model_path.read_bytes()).hexdigest()
    return AutoencoderPredictor(model, preprocessor, normalized, selected_seed, version, config, device)
