"""Load a trained 1D-CNN and predict from raw C-MAPSS engine histories."""

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
    "sire_cmapss_04_cnn1d_model", MODEL_DIR / "model.py"
)
if _MODEL_SPEC is None or _MODEL_SPEC.loader is None:
    raise ImportError("Cannot load CNN1D model definition")
_MODEL_MODULE = importlib.util.module_from_spec(_MODEL_SPEC)
sys.modules[_MODEL_SPEC.name] = _MODEL_MODULE
_MODEL_SPEC.loader.exec_module(_MODEL_MODULE)
CNN1DRegressor = _MODEL_MODULE.CNN1DRegressor


class CNN1DPredictor(PredictorBase):
    """Predict RUL from raw engine history using the saved 1D-CNN."""

    def __init__(
        self,
        model: CNN1DRegressor,
        preprocessor: CMapssPreprocessor,
        dataset: str,
        seed: int,
        version: str,
        window_length: int,
        rul_cap: float,
        device: torch.device,
    ) -> None:
        """Initialize the common history contract and CNN inference state."""
        super().__init__(
            preprocessor, "04_cnn1d", dataset, seed, version, window_length
        )
        self.network = model
        self.rul_cap = float(rul_cap)
        self.device = device

    def predict_window(self, window: np.ndarray) -> tuple[float, dict[str, Any]]:
        """Return the real-unit RUL prediction for one normalized window."""
        self.network.eval()
        tensor = torch.as_tensor(window, dtype=torch.float32, device=self.device)
        with torch.inference_mode():
            prediction = float(
                self.network(tensor).reshape(-1)[0].item() * self.rul_cap
            )
        return prediction, {}


def _artifact_paths(dataset: str, seed: int) -> tuple[Path, Path]:
    """Resolve trained weights and matching preprocessing artifact."""
    model_path = MODEL_DIR / "outputs" / dataset / f"seed_{seed}" / "best_model.pt"
    preprocessor_path = (
        cmapss_root() / "results" / "artifacts" / dataset / "preprocessor.joblib"
    )
    return model_path, preprocessor_path


def load_model(dataset: str, seed: int | None = None) -> CNN1DPredictor:
    """Load the saved CNN, config, and fitted preprocessing pipeline."""
    normalized = dataset.upper()
    selected_seed = int(seed if seed is not None else 42)
    model_path, preprocessor_path = _artifact_paths(normalized, selected_seed)
    config_path = model_path.parent / "config_used.yaml"
    missing = [
        path
        for path in (model_path, config_path, preprocessor_path)
        if not path.is_file()
    ]
    if missing:
        missing_paths = ", ".join(str(path) for path in missing)
        raise FileNotFoundError("Missing trained predictor artifacts: " + missing_paths)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    preprocessor = load_preprocessor(preprocessor_path)
    if preprocessor.dataset != normalized:
        raise ValueError(
            f"Preprocessor dataset {preprocessor.dataset} does not match {normalized}"
        )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    network = CNN1DRegressor(
        input_size=len(preprocessor.feature_columns),
        conv_channels=tuple(int(value) for value in config["conv_channels"]),
        conv_kernels=tuple(int(value) for value in config["conv_kernels"]),
        conv_dropout=float(config["conv_dropout"]),
        head_hidden_size=int(config["head_hidden_size"]),
        head_dropout=float(config["head_dropout"]),
    )
    state = torch.load(model_path, map_location="cpu", weights_only=True)
    network.load_state_dict(state)
    network.to(device).eval()
    version = hashlib.sha256(
        config_path.read_bytes() + model_path.read_bytes()
    ).hexdigest()
    return CNN1DPredictor(
        model=network,
        preprocessor=preprocessor,
        dataset=normalized,
        seed=selected_seed,
        version=version,
        window_length=int(config["window_length"]),
        rul_cap=float(config["rul_cap"]),
        device=device,
    )
