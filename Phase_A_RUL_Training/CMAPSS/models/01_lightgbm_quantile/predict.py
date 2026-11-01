"""Load quantile LightGBM intervals alongside the existing point predictor."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

MODEL_DIR = Path(__file__).resolve().parent
TRACK_ROOT = MODEL_DIR.parents[1]
for import_path in (TRACK_ROOT, TRACK_ROOT / "models" / "01_lightgbm"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from common.config import cmapss_root
from common.features import extract_window_features


def _load_baseline_predictor(dataset: str, seed: int) -> Any:
    """Load the unchanged baseline predictor by its source file path."""
    path = TRACK_ROOT / "models" / "01_lightgbm" / "predict.py"
    spec = importlib.util.spec_from_file_location(f"sire_quantile_base_{dataset}_{seed}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load baseline predictor at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.load_model(dataset, seed)


class LightGBMQuantilePredictor:
    """Add 0.1/0.9 quantile bounds to baseline LightGBM point predictions."""

    def __init__(self, baseline: Any, lower: lgb.Booster, upper: lgb.Booster, version: str) -> None:
        self.baseline = baseline
        self.lower = lower
        self.upper = upper
        self.dataset = baseline.dataset
        self.seed = baseline.seed
        self.version = version
        self.model = "01_lightgbm_quantile"

    def predict_rul(self, history: pd.DataFrame) -> dict[str, Any]:
        """Predict point RUL and a quantile-derived 80% interval from raw rows."""
        baseline_result = self.baseline.predict_rul(history)
        window, _, _ = self.baseline.prepare_window(history)
        condition_ids = None
        preprocessor = self.baseline.preprocessor
        if preprocessor.n_conditions > 1:
            if preprocessor.clusterer is None:
                raise RuntimeError("The fitted condition clusterer is missing")
            settings = window[0, -1, -len(preprocessor.setting_columns):].reshape(1, -1)
            settings = settings.astype(preprocessor.clusterer.cluster_centers_.dtype, copy=False)
            condition_ids = preprocessor.clusterer.predict(settings)
        features = extract_window_features(
            window,
            channel_names=preprocessor.feature_columns,
            condition_ids=condition_ids,
        )
        feature_names = self.lower.feature_name()
        features = features.loc[:, feature_names]
        q10 = float(self.lower.predict(features)[0])
        q90 = float(self.upper.predict(features)[0])
        result = dict(baseline_result)
        result.update({
            "model": self.model,
            "version": self.version,
            "interval_80": [min(q10, q90), max(q10, q90)],
            "uncertainty_method": "lightgbm_quantile_0.1_0.9",
        })
        return result


def load_model(dataset: str, seed: int | None = None) -> LightGBMQuantilePredictor:
    """Load the matching baseline point model and its two quantile artifacts."""
    normalized = dataset.upper()
    selected_seed = int(seed if seed is not None else 42)
    output = MODEL_DIR / "outputs" / normalized / f"seed_{selected_seed}"
    paths = (output / "quantile_10.txt", output / "quantile_90.txt")
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing quantile model artifacts: " + ", ".join(map(str, missing)))
    baseline = _load_baseline_predictor(normalized, selected_seed)
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return LightGBMQuantilePredictor(
        baseline,
        lgb.Booster(model_file=str(paths[0])),
        lgb.Booster(model_file=str(paths[1])),
        digest.hexdigest(),
    )
