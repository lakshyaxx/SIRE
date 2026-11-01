"""Load a trained transformer and predict from raw C-MAPSS histories."""

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
    "sire_cmapss_05_transformer_model", MODEL_DIR / "model.py"
)
if _MODEL_SPEC is None or _MODEL_SPEC.loader is None:
    raise ImportError("Cannot load transformer model definition")
_MODEL_MODULE = importlib.util.module_from_spec(_MODEL_SPEC)
sys.modules[_MODEL_SPEC.name] = _MODEL_MODULE
_MODEL_SPEC.loader.exec_module(_MODEL_MODULE)
TransformerRegressor = _MODEL_MODULE.TransformerRegressor


class TransformerPredictor(PredictorBase):
    """Predict RUL from raw engine history with the saved transformer."""

    def __init__(
        self,
        model: TransformerRegressor,
        preprocessor: CMapssPreprocessor,
        dataset: str,
        seed: int,
        version: str,
        window_length: int,
        rul_cap: float,
        device: torch.device,
    ) -> None:
        """Initialize the common history contract and transformer inference state."""
        super().__init__(
            preprocessor,
            "05_transformer",
            dataset,
            seed,
            version,
            window_length,
        )
        self.network = model
        self.rul_cap = float(rul_cap)
        self.device = device

    def predict_window(self, window: np.ndarray) -> tuple[float, dict[str, Any]]:
        """Return a real-unit RUL estimate from one normalized window."""
        self.network.eval()
        tensor = torch.as_tensor(window, dtype=torch.float32, device=self.device)
        with torch.inference_mode():
            prediction = float(
                self.network(tensor).reshape(-1)[0].item() * self.rul_cap
            )
        return prediction, {}


def _artifact_paths(dataset: str, seed: int) -> tuple[Path, Path]:
    """Resolve model weights and preprocessor without relying on cwd."""
    model_path = MODEL_DIR / "outputs" / dataset / f"seed_{seed}" / "best_model.pt"
    preprocessor_path = (
        cmapss_root() / "results" / "artifacts" / dataset / "preprocessor.joblib"
    )
    return model_path, preprocessor_path


def load_model(dataset: str, seed: int | None = None) -> TransformerPredictor:
    """Load transformer weights, config, and fitted preprocessing artifact."""
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
    network = TransformerRegressor(
        input_size=len(preprocessor.feature_columns),
        d_model=int(config["d_model"]),
        nhead=int(config["nhead"]),
        num_layers=int(config["num_layers"]),
        dim_feedforward=int(config["dim_feedforward"]),
        dropout=float(config["transformer_dropout"]),
        positional_max_len=int(config["positional_max_len"]),
        head_hidden_size=int(config["head_hidden_size"]),
        head_dropout=float(config["head_dropout"]),
    )
    state = torch.load(model_path, map_location="cpu", weights_only=True)
    network.load_state_dict(state)
    network.to(device).eval()
    version = hashlib.sha256(
        config_path.read_bytes() + model_path.read_bytes()
    ).hexdigest()
    return TransformerPredictor(
        model=network,
        preprocessor=preprocessor,
        dataset=normalized,
        seed=selected_seed,
        version=version,
        window_length=int(config["window_length"]),
        rul_cap=float(config["rul_cap"]),
        device=device,
    )
