"""Load the fitted ensemble and each member predictor for raw engine histories."""

from __future__ import annotations

import hashlib
import importlib.util
import json
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

from common.config import DATASET_IDS
from common.config import cmapss_root
from common.uncertainty import spread_interval


def _load_member_predictor(model_name: str, dataset: str, seed: int) -> Any:
    """Import a member's predictor by path and load its trained model."""
    module_path = TRACK_ROOT / "models" / model_name / "predict.py"
    if not module_path.is_file():
        raise FileNotFoundError(f"Member predictor does not exist: {module_path}")
    module_name = f"sire_member_{model_name}_{dataset}_{seed}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import member predictor {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.load_model(dataset, seed)


class EnsemblePredictor:
    """Combine raw-history outputs from the saved member models."""

    def __init__(
        self, dataset: str, seed: int, version: str, method: str,
        parameters: dict[str, Any], members: dict[str, Any], uncertainty_scale: float,
    ) -> None:
        """Store the selected ensemble method and its member predictors."""
        self.dataset = dataset.upper()
        self.seed = int(seed)
        self.version = version
        self.method = method
        self.parameters = parameters
        self.member_predictors = members
        self.model = "08_ensemble"
        self.uncertainty_scale = float(uncertainty_scale)

    def predict_rul(self, history: pd.DataFrame) -> dict[str, Any]:
        """Run every member and return the selected blend plus member predictions."""
        if not isinstance(history, pd.DataFrame) or history.empty:
            raise ValueError("history must be a non-empty pandas DataFrame")
        outputs = {
            name: predictor.predict_rul(history)
            for name, predictor in self.member_predictors.items()
        }
        predictions = np.asarray([outputs[name]["rul"] for name in self.member_predictors], dtype=float)
        if not np.isfinite(predictions).all():
            raise ValueError("member predictors returned non-finite RUL estimates")
        member_std = float(np.std(predictions, ddof=0))
        member_min = float(np.min(predictions))
        member_max = float(np.max(predictions))
        if self.method == "weighted_average":
            weights = np.asarray(self.parameters["weights"], dtype=float)
            if weights.shape != predictions.shape or np.any(weights < 0) or not np.isclose(weights.sum(), 1.0):
                raise ValueError("saved weighted-average parameters are invalid")
            rul = float(predictions @ weights)
        elif self.method == "stacking":
            coefficients = np.asarray(self.parameters["coefficients"], dtype=float)
            if coefficients.shape != predictions.shape or np.any(coefficients < -1e-10):
                raise ValueError("saved Ridge parameters are invalid")
            rul = float(predictions @ coefficients + float(self.parameters["intercept"]))
        else:
            raise ValueError(f"Unknown saved ensemble method {self.method!r}")
        lower, upper = spread_interval([rul], [member_std], self.uncertainty_scale)
        step_counts = [int(result["n_steps_used"]) for result in outputs.values()]
        warnings = list(dict.fromkeys(
            warning for result in outputs.values() for warning in result.get("warnings", [])
        ))
        return {
            "rul": rul,
            "rul_unit": "cycles",
            "n_steps_used": min(step_counts),
            "model": self.model,
            "dataset": self.dataset,
            "seed": self.seed,
            "version": self.version,
            "warnings": warnings,
            "members": outputs,
            "member_prediction_std": member_std,
            "member_prediction_min": member_min,
            "member_prediction_max": member_max,
            "interval_80": [float(lower[0]), float(upper[0])],
            "uncertainty_method": "validation_calibrated_member_spread_80",
        }


def load_model(dataset: str, seed: int | None = None) -> EnsemblePredictor:
    """Load the validation-selected ensemble and its member predictors."""
    normalized = dataset.upper()
    if normalized not in DATASET_IDS:
        raise ValueError(f"Unknown CMAPSS dataset {dataset!r}")
    selected_seed = int(seed if seed is not None else 42)
    calibration_path = (
        cmapss_root() / "results" / "artifacts" / normalized / "ensemble_uncertainty.json"
    )
    if not calibration_path.is_file():
        raise FileNotFoundError(f"Missing validation-fitted uncertainty calibration: {calibration_path}")
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    scale = float(calibration["spread_scale"])
    output = MODEL_DIR / "outputs" / normalized / f"seed_{selected_seed}"
    model_path = output / "best_model.json"
    config_path = output / "config_used.yaml"
    missing = [path for path in (model_path, config_path) if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing saved ensemble artifacts: " + ", ".join(map(str, missing)))
    params = json.loads(model_path.read_text(encoding="utf-8"))
    if params["dataset"] != normalized or int(params["seed"]) != selected_seed:
        raise ValueError("Saved ensemble identity does not match requested dataset and seed")
    members = {
        name: _load_member_predictor(name, normalized, selected_seed)
        for name in params["members"]
    }
    method = params["selected_method"]
    selected_parameters = params["selected_parameters"]
    version = hashlib.sha256(config_path.read_bytes() + model_path.read_bytes()).hexdigest()
    return EnsemblePredictor(
        normalized, selected_seed, version, method, selected_parameters, members, scale
    )
