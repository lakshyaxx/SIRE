"""Process-isolated adapter; never trains, fits or mutates legacy models."""

import importlib.util
import json
import math
import sys
from typing import Any

import pandas as pd

from app.core.config import TRACK
from app.prediction.hub import entry, verify_integrity


def validate_output(
    output: dict[str, Any], selected: dict[str, Any], history: pd.DataFrame
) -> None:
    """Validate native identity, units and optional intervals without changing any values."""
    key = "anomaly_score" if selected["task"] == "anomaly" else "rul"
    if (
        not math.isfinite(float(output[key]))
        or output["dataset"] != selected["dataset"]
        or int(output["seed"]) != selected["seed"]
    ):
        raise ValueError("Invalid native prediction identity or value")
    if selected["task"] == "anomaly":
        if "rul" in output or not math.isfinite(float(output["threshold"])):
            raise ValueError("Anomaly output must not masquerade as RUL")
    elif output.get("rul_unit") != "cycles" or not 0 < output["n_steps_used"] <= len(
        history
    ):
        raise ValueError("Invalid RUL units or step count")
    for key in ["interval_80", "interval_90"]:
        if key in output:
            bounds = output[key]
            if (
                len(bounds) != 2
                or not all(math.isfinite(float(value)) for value in bounds)
                or bounds[0] > bounds[1]
            ):
                raise ValueError("Invalid saved prediction interval")


def legacy_predict(model_id: str, history: pd.DataFrame) -> dict[str, Any]:
    """Load the exact registered module and call its original inference contract."""
    selected = entry(model_id)
    path = TRACK / selected["predict_module"]
    spec = importlib.util.spec_from_file_location("sire_isolated_predictor", path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot import preserved predictor")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if selected.get("variant") == "legacy_quantile":

        def original_point(dataset: str, seed: int) -> Any:
            """Pair archived quantiles with their original point model, not tuned weights."""
            point_path = TRACK / "models/01_lightgbm/predict.py"
            point_spec = importlib.util.spec_from_file_location(
                "sire_original_point", point_path
            )
            if point_spec is None or point_spec.loader is None:
                raise ImportError("Original point loader missing")
            point_module = importlib.util.module_from_spec(point_spec)
            sys.modules[point_spec.name] = point_module
            point_spec.loader.exec_module(point_module)
            point_module._artifact_paths = lambda dataset, seed: (
                TRACK
                / "artifacts/01_lightgbm/outputs"
                / dataset
                / f"seed_{seed}"
                / "model.txt",
                TRACK / "artifacts/common" / dataset / "preprocessor.joblib",
            )
            return point_module.load_model(dataset, seed)

        module._load_baseline_predictor = original_point
    if selected["family"] == "01_lightgbm" and selected["variant"] == "original":
        # Adapt only file resolution; retain the native model, config and feature logic.
        module._artifact_paths = lambda dataset, seed: (
            TRACK / selected["artifact_dir"] / "model.txt",
            TRACK / "artifacts/common" / dataset / "preprocessor.joblib",
        )
    predictor = module.load_model(selected["dataset"], selected["seed"])
    output = (
        predictor.score(history)
        if selected["task"] == "anomaly"
        else predictor.predict_rul(history)
    )
    validate_output(output, selected, history)
    return output


def main() -> None:
    """Read one validated parent request, verify artifacts and return one JSON line."""
    payload = json.load(sys.stdin)
    verify_integrity()
    output = legacy_predict(payload["model_id"], pd.DataFrame(payload["history"]))
    print("SIRE_RESULT=" + json.dumps(output, allow_nan=False))


if __name__ == "__main__":
    main()
