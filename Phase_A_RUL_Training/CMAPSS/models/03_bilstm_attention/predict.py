"""Load a trained BiLSTM attention model for raw C-MAPSS histories."""

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
    "sire_cmapss_03_bilstm_attention_model", MODEL_DIR / "model.py"
)
if _MODEL_SPEC is None or _MODEL_SPEC.loader is None:
    raise ImportError("Cannot load BiLSTM attention model definition")
_MODEL_MODULE = importlib.util.module_from_spec(_MODEL_SPEC)
sys.modules[_MODEL_SPEC.name] = _MODEL_MODULE
_MODEL_SPEC.loader.exec_module(_MODEL_MODULE)
BiLSTMAttentionRegressor = _MODEL_MODULE.BiLSTMAttentionRegressor


class BiLSTMAttentionPredictor(PredictorBase):
    """Predict raw-history RUL and expose model temporal attention weights."""

    def __init__(
        self,
        model: BiLSTMAttentionRegressor,
        preprocessor: CMapssPreprocessor,
        dataset: str,
        seed: int,
        version: str,
        window_length: int,
        rul_cap: float,
        device: torch.device,
    ) -> None:
        """Initialize the model and shared raw-history prediction contract."""
        super().__init__(
            preprocessor,
            "03_bilstm_attention",
            dataset,
            seed,
            version,
            window_length,
        )
        self.network = model
        self.rul_cap = float(rul_cap)
        self.device = device

    def predict_window(self, window: np.ndarray) -> tuple[float, dict[str, Any]]:
        """Predict RUL and return the attention vector aligned to the window."""
        self.network.eval()
        tensor = torch.as_tensor(window, dtype=torch.float32, device=self.device)
        with torch.inference_mode():
            prediction, attention = self.network(tensor, return_attention=True)
        weights = attention[0].cpu().numpy().astype(float).tolist()
        return float(prediction.reshape(-1)[0].item() * self.rul_cap), {
            "attention": weights
        }


def _artifact_paths(dataset: str, seed: int) -> tuple[Path, Path]:
    """Resolve weights and preprocessor independent of the working directory."""
    model_path = MODEL_DIR / "outputs" / dataset / f"seed_{seed}" / "best_model.pt"
    preprocessor_path = (
        cmapss_root() / "results" / "artifacts" / dataset / "preprocessor.joblib"
    )
    return model_path, preprocessor_path


def load_model(dataset: str, seed: int | None = None) -> BiLSTMAttentionPredictor:
    """Load model weights, run config, and its train-fitted preprocessor."""
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
    network = BiLSTMAttentionRegressor(
        input_size=len(preprocessor.feature_columns),
        hidden_size=int(config["hidden_size"]),
        num_layers=int(config["num_layers"]),
        encoder_dropout=float(config["encoder_dropout"]),
        attention_size=int(config["attention_size"]),
        head_hidden_size=int(config["head_hidden_size"]),
        head_dropout=float(config["head_dropout"]),
    )
    state = torch.load(model_path, map_location="cpu", weights_only=True)
    network.load_state_dict(state)
    network.to(device).eval()
    version = hashlib.sha256(
        config_path.read_bytes() + model_path.read_bytes()
    ).hexdigest()
    return BiLSTMAttentionPredictor(
        model=network,
        preprocessor=preprocessor,
        dataset=normalized,
        seed=selected_seed,
        version=version,
        window_length=int(config["window_length"]),
        rul_cap=float(config["rul_cap"]),
        device=device,
    )
