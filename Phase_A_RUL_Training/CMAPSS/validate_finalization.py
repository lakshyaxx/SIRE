"""Check completeness and registry paths after CMAPSS finalization."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from common.config import DATASET_IDS, cmapss_root


def main() -> None:
    """Validate seed coverage, derived validation files, and registry paths."""
    root = cmapss_root()
    comparison = pd.read_csv(root / "results" / "comparison.csv")
    registry = json.loads((root / "model_registry.json").read_text(encoding="utf-8"))
    models = tuple(registry["datasets"][DATASET_IDS[0]]["models"])
    seeds = (42, 43, 44)
    missing: list[tuple[str, str, int, str]] = []
    for dataset in DATASET_IDS:
        for model in models:
            for seed in seeds:
                for target in ("raw", "clipped"):
                    rows = comparison.loc[
                        comparison.dataset.eq(dataset)
                        & comparison.model.eq(model)
                        & comparison.seed.eq(seed)
                        & comparison.split.eq("test")
                        & comparison.target_type.eq(target)
                    ]
                    if len(rows) != 1:
                        missing.append((dataset, model, seed, target))
    if missing:
        raise AssertionError(f"Missing or duplicate test comparison rows: {missing}")
    val_last_files = list(root.glob("models/*/outputs/*/seed_*/predictions_val_last.csv"))
    expected_val_last = len(DATASET_IDS) * len(models) * len(seeds)
    if len(val_last_files) != expected_val_last:
        raise AssertionError(
            f"Expected {expected_val_last} val_last files, found {len(val_last_files)}"
        )
    for dataset in DATASET_IDS:
        entries = registry["datasets"][dataset]["models"]
        if tuple(entries) != models:
            raise AssertionError(f"Model registry differs for {dataset}")
        if registry["datasets"][dataset]["health_indicator_model"] != "06_autoencoder":
            raise AssertionError(f"Wrong health indicator model for {dataset}")
        for model, entry in entries.items():
            if not (root / entry["predict_module"]).is_file():
                raise FileNotFoundError(root / entry["predict_module"])
            if not (root / entry["artifact_dir"]).is_dir():
                raise FileNotFoundError(root / entry["artifact_dir"])
        uncertainty = registry["datasets"][dataset].get("uncertainty", {})
        required_uncertainty = {"08_ensemble_member_spread", "01_lightgbm_quantile"}
        if set(uncertainty) != required_uncertainty:
            raise AssertionError(f"Uncertainty registry entries differ for {dataset}: {sorted(uncertainty)}")
        for predictor_name, entry in uncertainty.items():
            if not (root / entry["predict_module"]).is_file():
                raise FileNotFoundError(root / entry["predict_module"])
            if predictor_name == "01_lightgbm_quantile" and not (root / entry["artifact_dir"]).is_dir():
                raise FileNotFoundError(root / entry["artifact_dir"])
            if predictor_name == "08_ensemble_member_spread" and not (root / entry["calibration_artifact"]).is_file():
                raise FileNotFoundError(root / entry["calibration_artifact"])
    report = (root / "results" / "REPORT.md").read_text(encoding="utf-8")
    for required_text in ("±", "R²", "Hardest dataset", "Autoencoder onset diagnostics"):
        if required_text not in report:
            raise AssertionError(f"Report is missing {required_text!r}")
    print(
        f"comparison test rows: {len(DATASET_IDS) * len(models) * len(seeds) * 2}; "
        f"val_last files: {len(val_last_files)}; registry model entries: "
        f"{len(DATASET_IDS) * len(models)}; uncertainty predictors: "
        f"{len(DATASET_IDS) * len(required_uncertainty)}; UTF-8 report markers: present"
    )


if __name__ == "__main__":
    main()
