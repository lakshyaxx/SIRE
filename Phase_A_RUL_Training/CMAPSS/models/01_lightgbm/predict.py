"""Load a trained LightGBM model and predict from raw engine histories."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml

MODEL_DIR = Path(__file__).resolve().parent
TRACK_ROOT = MODEL_DIR.parents[1]
for import_path in (TRACK_ROOT, MODEL_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from common.config import cmapss_root
from common.features import extract_window_features
from common.predictor_base import PredictorBase
from common.preprocess import CMapssPreprocessor, load_preprocessor

from model import aggregate_channel_contributions


class LightGBMPredictor(PredictorBase):
    """Predictor that derives LightGBM features from the latest raw window."""

    def __init__(
        self,
        booster: lgb.Booster,
        preprocessor: CMapssPreprocessor,
        dataset: str,
        seed: int,
        version: str,
        window_length: int,
    ) -> None:
        super().__init__(preprocessor, "01_lightgbm", dataset, seed, version, window_length)
        self.booster = booster
        self.feature_names = list(booster.feature_name())

    def predict_window(self, window: np.ndarray) -> tuple[float, dict[str, Any]]:
        """Predict one window and return top signed channel contributions."""
        condition_ids = None
        if self.preprocessor.n_conditions > 1:
            if self.preprocessor.clusterer is None:
                raise RuntimeError("The fitted condition clusterer is missing")
            setting_values = window[
                0, -1, -len(self.preprocessor.setting_columns) :
            ].reshape(1, -1)
            setting_values = setting_values.astype(
                self.preprocessor.clusterer.cluster_centers_.dtype, copy=False
            )
            condition_ids = self.preprocessor.clusterer.predict(setting_values)
        features = extract_window_features(
            window,
            channel_names=self.preprocessor.feature_columns,
            condition_ids=condition_ids,
        )
        features = features.loc[:, self.feature_names]
        prediction = float(self.booster.predict(features)[0])
        contributions = self.booster.predict(features, pred_contrib=True)
        top = aggregate_channel_contributions(
            contributions,
            self.feature_names,
            self.preprocessor.feature_columns,
        )[:5]
        return prediction, {"top_contributors": top}


def _artifact_paths(dataset: str, seed: int) -> tuple[Path, Path]:
    """Resolve saved model and matching preprocessor paths without cwd dependence."""
    model_path = MODEL_DIR / "outputs" / dataset / f"seed_{seed}" / "model.txt"
    preprocessor_path = cmapss_root() / "results" / "artifacts" / dataset / "preprocessor.joblib"
    return model_path, preprocessor_path


def load_model(dataset: str, seed: int | None = None) -> LightGBMPredictor:
    """Load the requested trained model, config, and shared preprocessor."""
    normalized = dataset.upper()
    selected_seed = int(seed if seed is not None else 42)
    model_path, preprocessor_path = _artifact_paths(normalized, selected_seed)
    config_path = model_path.parent / "config_used.yaml"
    missing = [path for path in (model_path, config_path, preprocessor_path) if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing trained predictor artifacts: " + ", ".join(str(path) for path in missing))
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    preprocessor = load_preprocessor(preprocessor_path)
    if preprocessor.dataset != normalized:
        raise ValueError(f"Preprocessor dataset {preprocessor.dataset} does not match requested {normalized}")
    version_hash = hashlib.sha256()
    version_hash.update(config_path.read_bytes())
    with model_path.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
            version_hash.update(chunk)
    return LightGBMPredictor(
        booster=lgb.Booster(model_file=str(model_path)),
        preprocessor=preprocessor,
        dataset=normalized,
        seed=selected_seed,
        version=version_hash.hexdigest(),
        window_length=int(config["window_length"]),
    )
