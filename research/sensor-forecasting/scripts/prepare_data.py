"""Prepare configured C-MAPSS train/validation/test windows."""
import argparse
import json

import numpy as np
import pandas as pd
import yaml

from pdm.common.paths import CONFIG_DIR, PROCESSED_DIR, resolve_path
from pdm.data.loaders.cmapss_loader import CMapssLoader
from pdm.data.preprocessing import CMapssPreprocessor
from pdm.data.rul_labels import add_rul_labels, add_test_rul_labels
from pdm.data.splits import split_units
from pdm.data.validators import validate_cmapss
from pdm.data.windowing import make_windows


def prepare(subset: str | None = None) -> dict:
    """Run the configured C-MAPSS data preparation pipeline and save artifacts."""
    with (CONFIG_DIR / "data" / "cmapss.yaml").open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    with (CONFIG_DIR / "data" / "active.yaml").open(encoding="utf-8") as stream:
        active = yaml.safe_load(stream)
    subset = (subset or active["subset"]).upper()
    raw_dir = resolve_path(config["raw_dir"])
    loader = CMapssLoader(raw_dir)
    train = loader.load_train(subset)
    test, final_rul = loader.load_test(subset)
    validate_cmapss(train)
    validate_cmapss(test, require_complete=False)
    train = add_rul_labels(train, int(config.get("rul_clip", 125)))
    train_units = np.sort(train["unit"].unique())
    train_ids, val_ids = split_units(train_units, float(config.get("val_fraction_units", 0.2)), int(config.get("seed", 42)))
    train_units_split, val_units_split = train_units[train_ids], train_units[val_ids]
    train_rows = train[train.unit.isin(train_units_split)].copy()
    val_rows = train[train.unit.isin(val_units_split)].copy()
    preprocessor = CMapssPreprocessor(
        config.get("scaler", "minmax"),
        bool(config.get("per_condition_normalization", False)),
        int(config.get("operating_conditions", 6)),
        int(config.get("seed", 42)),
    )
    train_scaled = preprocessor.fit_transform(train_rows)
    val_scaled = preprocessor.transform(val_rows)
    test_labeled = add_test_rul_labels(test, final_rul, int(config.get("rul_clip", 125)))
    test_scaled = preprocessor.transform(test_labeled)
    features = preprocessor.features
    win = int(config.get("window_size", 30))
    stride = int(config.get("window_stride", 1))
    X_train, y_train, units_train = make_windows(train_scaled, features, win, stride)
    X_val, y_val, units_val = make_windows(val_scaled, features, win, stride)
    X_test, y_test, units_test = make_windows(test_scaled, features, win, stride)
    test_engine_units = np.sort(test["unit"].unique())
    test_rul_raw = final_rul.reindex(test_engine_units).to_numpy(dtype=np.float32)
    out_dir = PROCESSED_DIR / "cmapss" / subset.lower()
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, array in (("X_train", X_train), ("y_train", y_train), ("X_val", X_val), ("y_val", y_val), ("X_test", X_test), ("y_test", y_test)):
        np.save(out_dir / f"{name}.npy", array)
    for name, array in (("units_train", units_train), ("units_val", units_val), ("units_test", units_test)):
        np.save(out_dir / f"{name}.npy", array)
    np.save(out_dir / "test_engine_units.npy", test_engine_units)
    np.save(out_dir / "test_rul_raw.npy", test_rul_raw)
    pd.to_pickle(preprocessor, out_dir / "preprocessor.pkl")
    metadata = {"subset": subset, "features": features, "dropped_constant": preprocessor.constant_features,
                "train_units": train_units_split.tolist(), "val_units": val_units_split.tolist(),
                "test_units": test_engine_units.tolist(),
                "window_counts": {"train": int(len(X_train)), "val": int(len(X_val)), "test": int(len(X_test))},
                "engine_counts": {"train": int(len(train_units_split)), "val": int(len(val_units_split)), "test": int(test.unit.nunique())},
                "shapes": {"X_train": list(X_train.shape), "y_train": list(y_train.shape),
                           "X_val": list(X_val.shape), "y_val": list(y_val.shape),
                           "X_test": list(X_test.shape), "y_test": list(y_test.shape)}}
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", help="Override active.yaml subset (FD001-FD004)")
    args = parser.parse_args()
    print(json.dumps(prepare(args.subset), indent=2))


if __name__ == "__main__":
    main()
