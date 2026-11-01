"""Load every registered CMAPSS predictor from another cwd and smoke-test raw rows."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(__file__).resolve().parents[1] / ".venv" / "mplconfig"),
)

import numpy as np
import pandas as pd

from common.config import DATASET_IDS, RAW_COLUMNS, cmapss_root


def _load_module(path: Path, name: str) -> Any:
    """Import a predictor module directly from its registered path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load predictor module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_registry() -> list[dict[str, Any]]:
    """Run all registry entries on the first official test engine per dataset."""
    root = cmapss_root()
    registry = json.loads((root / "model_registry.json").read_text(encoding="utf-8"))
    original_cwd = Path.cwd().resolve()
    other_cwd = Path(tempfile.gettempdir()).resolve()
    if other_cwd == original_cwd:
        other_cwd = root.parent.resolve()
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    os.chdir(other_cwd)
    try:
        for dataset in DATASET_IDS:
            data = pd.read_csv(
                root / "data" / f"test_{dataset}.txt",
                sep=r"\s+",
                header=None,
                names=RAW_COLUMNS,
            )
            first_unit = int(data.unit.min())
            raw_history = data.loc[data.unit.eq(first_unit)].copy()
            for model_name, entry in registry["datasets"][dataset]["models"].items():
                try:
                    module_path = root / entry["predict_module"]
                    predictor_module = _load_module(
                        module_path, f"sire_registry_{dataset}_{model_name}"
                    )
                    predictor = predictor_module.load_model(dataset, int(entry["seed"]))
                    output = predictor.predict_rul(raw_history)
                    rul = float(output["rul"])
                    if not np.isfinite(rul):
                        raise ValueError(f"non-finite RUL output {rul}")
                    if output.get("dataset") != dataset or int(output.get("seed")) != int(entry["seed"]):
                        raise ValueError("prediction identity does not match registry entry")
                    if model_name == "08_ensemble":
                        _validate_interval(output)
                    row = {
                        "dataset": dataset,
                        "model": model_name,
                        "engine": first_unit,
                        "seed": int(entry["seed"]),
                        "rul": rul,
                        "cwd": str(Path.cwd()),
                    }
                    results.append(row)
                    print(json.dumps(row, sort_keys=True))
                except Exception as exc:  # report all model failures in one run
                    failure = f"{dataset}/{model_name}: {type(exc).__name__}: {exc}"
                    failures.append(failure)
                    print(f"FAIL {failure}", file=sys.stderr)
            for uncertainty_name, entry in registry["datasets"][dataset].get("uncertainty", {}).items():
                try:
                    module_path = root / entry["predict_module"]
                    predictor_module = _load_module(
                        module_path, f"sire_uncertainty_{dataset}_{uncertainty_name}"
                    )
                    if uncertainty_name == "01_lightgbm_quantile":
                        seed = int(entry["seed"])
                    else:
                        seed = int(registry["datasets"][dataset]["models"]["08_ensemble"]["seed"])
                    predictor = predictor_module.load_model(dataset, seed)
                    output = predictor.predict_rul(raw_history)
                    _validate_interval(output)
                    row = {
                        "dataset": dataset,
                        "model": uncertainty_name,
                        "engine": first_unit,
                        "seed": seed,
                        "rul": float(output["rul"]),
                        "interval_80": output["interval_80"],
                        "uncertainty_method": output["uncertainty_method"],
                        "cwd": str(Path.cwd()),
                    }
                    if not np.isfinite(row["rul"]):
                        raise ValueError("uncertainty predictor returned non-finite point RUL")
                    results.append(row)
                    print(json.dumps(row, sort_keys=True))
                except Exception as exc:
                    failure = f"{dataset}/{uncertainty_name}: {type(exc).__name__}: {exc}"
                    failures.append(failure)
                    print(f"FAIL {failure}", file=sys.stderr)
    finally:
        os.chdir(original_cwd)
    print(f"Loaded {len(results)} registered predictors; failures={len(failures)}")
    if failures:
        raise RuntimeError("Registry predictor failures: " + "; ".join(failures))
    return results


def _validate_interval(output: dict[str, Any]) -> None:
    """Reject malformed uncertainty fields returned by a registered predictor."""
    interval = np.asarray(output.get("interval_80"), dtype=float)
    if interval.shape != (2,) or not np.isfinite(interval).all() or interval[0] > interval[1]:
        raise ValueError(f"invalid interval_80: {output.get('interval_80')}")
    if not output.get("uncertainty_method"):
        raise ValueError("uncertainty_method is missing")


if __name__ == "__main__":
    verify_registry()
