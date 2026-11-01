"""Fit validation-selected LightGBM 0.1/0.9 quantile interval models."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

MODEL_DIR = Path(__file__).resolve().parent
TRACK_ROOT = MODEL_DIR.parents[1]
if str(TRACK_ROOT) not in sys.path:
    sys.path.insert(0, str(TRACK_ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(TRACK_ROOT.parents[0] / ".venv" / "mplconfig"))

import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml

from common.config import DATASET_IDS, cmapss_root, get_dataset_spec
from common.data import load_cmapss_dataset
from common.features import features_from_window_set
from common.preprocess import load_preprocessor
from common.splits import get_or_create_split
from common.windows import make_test_last_windows, make_windows

LOG = logging.getLogger("lightgbm_quantile_train")
BASE_MODEL_DIR = MODEL_DIR.parent / "01_lightgbm"


def _build_features(dataset: str) -> tuple[Any, Any, Any, Any, np.ndarray, np.ndarray]:
    """Build the same train/validation/test engineered windows as LightGBM."""
    config = yaml.safe_load((BASE_MODEL_DIR / "config.yaml").read_text(encoding="utf-8"))
    source = load_cmapss_dataset(dataset, rul_cap=int(config["rul_cap"]))
    split = get_or_create_split(
        dataset,
        source.train.unit.astype(int).unique().tolist(),
        val_fraction=float(config["val_fraction"]),
        seed=int(config["split_seed"]),
    )
    preprocessor = load_preprocessor(
        cmapss_root() / "results" / "artifacts" / dataset / "preprocessor.joblib"
    )
    transformed_train = preprocessor.transform(source.train)
    transformed_test = preprocessor.transform(source.test)
    train_rows = transformed_train.loc[transformed_train.unit.isin(split.train_units)]
    val_rows = transformed_train.loc[transformed_train.unit.isin(split.val_units)]
    length, stride = int(config["window_length"]), int(config["stride"])
    train_windows = make_windows(train_rows, preprocessor.feature_columns, length, stride)
    val_windows = make_windows(val_rows, preprocessor.feature_columns, length, stride)
    test_windows = make_test_last_windows(transformed_test, preprocessor.feature_columns, length)
    use_conditions = preprocessor.n_conditions > 1
    x_train = features_from_window_set(
        train_windows.x, preprocessor.feature_columns,
        train_windows.condition_ids if use_conditions else None,
    )
    x_val = features_from_window_set(
        val_windows.x, preprocessor.feature_columns,
        val_windows.condition_ids if use_conditions else None,
    )
    x_test = features_from_window_set(
        test_windows.x, preprocessor.feature_columns,
        test_windows.condition_ids if use_conditions else None,
    )
    feature_config = json.loads(
        (cmapss_root() / "results" / "artifacts" / dataset / "feature_config.json").read_text(encoding="utf-8")
    )
    if x_train.columns.tolist() != feature_config["feature_names"]:
        raise ValueError(f"Quantile feature schema differs from 01_lightgbm on {dataset}")
    truth = source.test_truth.set_index("unit").loc[test_windows.units]
    return (
        (config, train_windows, val_windows, test_windows, x_train, x_val, x_test),
        preprocessor,
        source,
        truth,
        truth.rul_raw.to_numpy(dtype=float),
        truth.rul_clipped.to_numpy(dtype=float),
    )


def _fit_quantile(
    config: dict[str, Any], x_train: pd.DataFrame, y_train: np.ndarray,
    x_val: pd.DataFrame, y_val: np.ndarray, seed: int, alpha: float,
) -> lgb.LGBMRegressor:
    """Fit a quantile LightGBM model with validation-only early stopping."""
    params = {
        "objective": "quantile",
        "alpha": alpha,
        "metric": "quantile",
        "learning_rate": float(config["learning_rate"]),
        "num_leaves": int(config["num_leaves"]),
        "min_data_in_leaf": int(config["min_data_in_leaf"]),
        "feature_fraction": float(config["feature_fraction"]),
        "bagging_fraction": float(config["bagging_fraction"]),
        "bagging_freq": int(config["bagging_freq"]),
        "lambda_l2": float(config["lambda_l2"]),
        "n_estimators": int(config["n_estimators"]),
        "verbosity": int(config.get("verbosity", -1)),
        "n_jobs": int(config.get("n_jobs", -1)),
        "random_state": int(seed),
        "bagging_seed": int(seed),
        "feature_fraction_seed": int(seed),
        "data_random_seed": int(seed),
        "deterministic": bool(config.get("deterministic", True)),
        "force_col_wise": bool(config.get("force_col_wise", True)),
        "device_type": "cpu",
    }
    model = lgb.LGBMRegressor(**params)
    model.fit(
        x_train,
        y_train,
        eval_set=[(x_val, y_val)],
        eval_metric="quantile",
        callbacks=[
            lgb.early_stopping(int(config["early_stopping_rounds"]), verbose=False),
            lgb.log_evaluation(period=0),
        ],
    )
    return model


def train_one(dataset: str, seed: int) -> Path:
    """Fit both quantiles for one dataset/seed and save interval predictions."""
    prepared, _, _, _, y_test_raw, y_test_clipped = _build_features(dataset)
    config, train_windows, val_windows, test_windows, x_train, x_val, x_test = prepared
    train_dir = BASE_MODEL_DIR / "outputs" / dataset / f"seed_{seed}"
    base_metrics = json.loads((train_dir / "metrics.json").read_text(encoding="utf-8"))
    point_model = lgb.Booster(model_file=str(train_dir / "model.txt"))
    point_val = point_model.predict(x_val, num_threads=-1)
    point_test = point_model.predict(x_test, num_threads=-1)
    quantile_models: dict[float, lgb.LGBMRegressor] = {}
    output = MODEL_DIR / "outputs" / dataset / f"seed_{seed}"
    output.mkdir(parents=True, exist_ok=True)
    for alpha in (0.1, 0.9):
        quantile_models[alpha] = _fit_quantile(
            config, x_train, train_windows.y, x_val, val_windows.y, seed, alpha
        )
        quantile_models[alpha].booster_.save_model(
            str(output / f"quantile_{int(alpha * 100):02d}.txt"),
            num_iteration=quantile_models[alpha].best_iteration_ or 0,
        )
    val_bounds = np.sort(np.column_stack([
        quantile_models[0.1].predict(x_val), quantile_models[0.9].predict(x_val)
    ]), axis=1)
    test_bounds = np.sort(np.column_stack([
        quantile_models[0.1].predict(x_test), quantile_models[0.9].predict(x_test)
    ]), axis=1)
    val_raw = val_windows.y_raw if val_windows.y_raw is not None else val_windows.y
    val_frame = pd.DataFrame({
        "unit": val_windows.units.astype(int), "step": val_windows.steps.astype(int),
        "y_true_raw": val_raw.astype(float), "y_true_clipped": val_windows.y.astype(float),
        "y_pred": np.asarray(point_val, dtype=float), "y_lower": val_bounds[:, 0],
        "y_upper": val_bounds[:, 1], "split": "val",
    })
    test_frame = pd.DataFrame({
        "unit": test_windows.units.astype(int), "step": test_windows.steps.astype(int),
        "y_true_raw": y_test_raw, "y_true_clipped": y_test_clipped,
        "y_pred": np.asarray(point_test, dtype=float), "y_lower": test_bounds[:, 0],
        "y_upper": test_bounds[:, 1], "split": "test",
    })
    val_frame.to_csv(output / "predictions_val.csv", index=False)
    test_frame.to_csv(output / "predictions_test.csv", index=False)
    config_used = dict(config)
    config_used.update({"model": "01_lightgbm_quantile", "dataset": dataset, "seed": seed, "quantiles": [0.1, 0.9]})
    (output / "config_used.yaml").write_text(yaml.safe_dump(config_used, sort_keys=False), encoding="utf-8")
    summary = {
        "dataset": dataset, "model": "01_lightgbm_quantile", "seed": seed,
        "base_seed_best_iteration": int(base_metrics["best_iteration"]),
        "quantile_best_iterations": {
            str(alpha): int(model.best_iteration_ or model.n_estimators)
            for alpha, model in quantile_models.items()
        },
        "feature_names": x_train.columns.tolist(),
        "n_train_windows": int(len(train_windows)),
        "n_val_windows": int(len(val_windows)),
    }
    (output / "metrics.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOG.info(
        "%s seed=%d fitted quantiles; best iterations q10=%d q90=%d",
        dataset, seed, summary["quantile_best_iterations"]["0.1"], summary["quantile_best_iterations"]["0.9"],
    )
    return output


def main(argv: list[str] | None = None) -> int:
    """Fit quantile predictors for requested subsets and fixed seeds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=(*DATASET_IDS, "all"), default="all")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    datasets = DATASET_IDS if args.dataset == "all" else (args.dataset,)
    for dataset in datasets:
        for seed in args.seeds:
            train_one(dataset, seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
