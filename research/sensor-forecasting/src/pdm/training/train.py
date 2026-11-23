"""Train seeded LightGBM baselines and evaluate engine-held-out validation."""
import argparse
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yaml

from pdm.common.paths import CONFIG_DIR, PROCESSED_DIR, DOCS_DIR, resolve_path
from pdm.evaluation.metrics import regression_metrics
from pdm.features.engineering import window_features
from pdm.models.lightgbm_model import LightGBMRULRegressor


def _load_arrays(subset: str) -> dict[str, np.ndarray]:
    folder = PROCESSED_DIR / "cmapss" / subset.lower()
    required = ["X_train", "y_train", "X_val", "y_val", "X_test", "y_test",
                "units_train", "units_val", "units_test", "test_engine_units", "test_rul_raw"]
    arrays = {name: np.load(folder / f"{name}.npy", allow_pickle=False) for name in required}
    return arrays


def _terminal_indices(units: np.ndarray) -> np.ndarray:
    """Select the final chronological window for each sorted engine's window stream."""
    return np.r_[np.flatnonzero(units[:-1] != units[1:]), len(units) - 1]


def train(config_path: str | None = None, subset: str | None = None, evaluate_test: bool = True) -> dict:
    """Train three seeded models, report validation and final official test metrics."""
    path = resolve_path(config_path) if config_path else CONFIG_DIR / "models" / "lightgbm.yaml"
    with path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    subset = (subset or config.get("dataset", "FD001")).upper()
    data = _load_arrays(subset)
    with (PROCESSED_DIR / "cmapss" / subset.lower() / "metadata.json").open(encoding="utf-8") as stream:
        metadata = json.load(stream)
    features = metadata["features"]
    forbidden = {"unit", "cycle", "rul", "max_cycle", "engine_max_cycle"}
    if forbidden.intersection(features):
        raise ValueError(f"Target or future-derived columns found in input features: {forbidden.intersection(features)}")
    x_train = window_features(data["X_train"], features)
    x_val = window_features(data["X_val"], features)
    x_test = window_features(data["X_test"], features)
    train_dir = resolve_path(config.get("output_dir", "models_store/lightgbm")) / subset.lower()
    metrics_dir = resolve_path(config.get("metrics_dir", "results/metrics"))
    train_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    terminal_val = _terminal_indices(data["units_val"])
    terminal_test = _terminal_indices(data["units_test"])
    train_units = set(metadata["train_units"])
    val_units = set(metadata["val_units"])
    if not train_units.isdisjoint(val_units):
        raise ValueError("Engine leakage: training and validation units overlap")
    if set(data["units_train"]) != train_units or set(data["units_val"]) != val_units:
        raise ValueError("Prepared window unit IDs do not match split metadata")
    run_metrics, test_predictions = [], []
    base_params = dict(config.get("params", {}))
    for seed in config.get("seeds", [config.get("seed", 42)]):
        params = {**base_params, "random_state": int(seed), "bagging_seed": int(seed),
                  "feature_fraction_seed": int(seed), "data_random_seed": int(seed)}
        model = LightGBMRULRegressor(**params)
        model.fit(x_train, data["y_train"])
        val_pred = model.predict(x_val)
        all_window_scores = regression_metrics(data["y_val"], val_pred)
        terminal_scores = regression_metrics(data["y_val"][terminal_val], val_pred[terminal_val])
        run_metrics.append({"seed": int(seed), "validation_all_windows": all_window_scores,
                            "validation_last_window_per_engine": terminal_scores})
        model.save(train_dir / f"model_seed_{seed}.txt")
        if evaluate_test:
            test_predictions.append(model.predict(x_test)[terminal_test])
    result = {"dataset": subset, "config": config, "features": list(x_train.columns),
              "split_units": {"train": metadata["train_units"], "validation": metadata["val_units"]},
              "window_feature_count": int(x_train.shape[1]),
              "dependency_versions": _dependency_versions(), "split": "engine_holdout",
              "test_used_for_training_or_tuning": False, "early_stopping": False,
              "validation_runs": run_metrics,
              "validation_all_windows_mean": _mean_metrics(run_metrics, "validation_all_windows"),
              "validation_last_window_mean": _mean_metrics(run_metrics, "validation_last_window_per_engine")}
    if evaluate_test:
        test_pred = np.mean(test_predictions, axis=0)
        test_units = data["units_test"][terminal_test]
        if not np.array_equal(test_units, data["test_engine_units"]):
            raise ValueError("Terminal test windows are not aligned with raw engine-level RUL values")
        raw_rul = data["test_rul_raw"]
        clipped_rul = np.minimum(raw_rul, int(config.get("rul_clip", 125)))
        result["official_test"] = {
            "reference": "raw RUL_FDxxx.txt values; separate clipped_125 result uses min(raw RUL, 125)",
            "unclipped": regression_metrics(raw_rul, test_pred),
            "clipped_125": regression_metrics(clipped_rul, test_pred),
        }
        result["official_test_engines"] = int(len(terminal_test))
        np.save(metrics_dir / f"{subset.lower()}_test_predictions.npy", test_pred)
    result["created_utc"] = datetime.now(timezone.utc).isoformat()
    output = metrics_dir / f"{subset.lower()}_lightgbm_metrics.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    _log_experiment(result, config)
    return result


def _mean_metrics(runs: list[dict], key: str) -> dict[str, float]:
    """Average the named metric set across the configured seeds."""
    return {name: float(np.mean([run[key][name] for run in runs])) for name in runs[0][key]}


def _dependency_versions() -> dict[str, str]:
    import lightgbm
    import sklearn
    return {"numpy": np.__version__, "pandas": pd.__version__, "scikit-learn": sklearn.__version__, "lightgbm": lightgbm.__version__}


def _log_experiment(result: dict, config: dict) -> None:
    log = DOCS_DIR / "experiment_log.md"
    date = datetime.now().astimezone().date().isoformat()
    rows = []
    for run in result["validation_runs"]:
        for metric_name, label in (("validation_all_windows", "validation all windows"),
                                   ("validation_last_window_per_engine", "validation terminal per engine")):
            m = run[metric_name]
            rows.append(f"| {date} | C-MAPSS/{result['dataset']} | LightGBM {label} | {run['seed']} | {m['rmse']:.4f} | {m['nasa_score']:.4f} | MAE {m['mae']:.4f}; engine holdout; window {config.get('window_size')} |")
    test = result.get("official_test")
    if test:
        for key, label in (("unclipped", "raw RUL"), ("clipped_125", "RUL clipped at 125")):
            m = test[key]
            rows.append(f"| {date} | C-MAPSS/{result['dataset']} | LightGBM official test {label} | ensemble | {m['rmse']:.4f} | {m['nasa_score']:.4f} | MAE {m['mae']:.4f}; terminal window per engine |")
    with log.open("a", encoding="utf-8") as stream:
        stream.write("\n" + "\n".join(rows) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="lightgbm", choices=["lightgbm"])
    parser.add_argument("--config")
    parser.add_argument("--subset", choices=["FD001", "FD002", "FD003", "FD004"])
    parser.add_argument("--no-test", action="store_true", help="Skip official test scoring")
    args = parser.parse_args()
    print(json.dumps(train(args.config, args.subset, not args.no_test), indent=2))


if __name__ == "__main__":
    main()
