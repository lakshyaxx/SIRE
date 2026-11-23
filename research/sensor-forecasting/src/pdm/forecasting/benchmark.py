"""Run selected sensor forecasting models on a common fixed-origin benchmark."""
import argparse
import json
import logging
from pathlib import Path
from time import perf_counter
import warnings

import numpy as np
import pandas as pd

from pdm.common.paths import resolve_path
from pdm.data.loaders.cmapss_loader import CMapssLoader
from pdm.evaluation.sensor_metrics import score_sensor_forecast
from pdm.forecasting.benchmark_data import known_regressors, read_settings, split_history
from pdm.forecasting.benchmark_reports import comparison_report, model_figures
from pdm.forecasting.sensor_experiment import new_run_directory
from pdm.models.statistical import MULTIVARIATE, STATISTICAL, fit_statistical

LOGGER = logging.getLogger(__name__)


def _run_tft(frame: pd.DataFrame, unit: int, targets: list[str], history: pd.DataFrame,
             actual: pd.DataFrame, config: dict, directory: Path, resume: Path | None) -> tuple:
    from pdm.models.tft import fit_tft

    seeds = config["seeds"]
    if not seeds or len(seeds) != len(set(seeds)) or (resume and len(seeds) != 1):
        raise ValueError("Use distinct seeds; resuming requires a single configured seed")
    predictions, seed_scores = [], []
    training, inference = 0.0, 0.0
    for seed in seeds:
        LOGGER.info("Training TFT seed %s", seed)
        started = perf_counter()
        fit = fit_tft(frame, unit, targets, len(actual), config, seed, directory / f"tft-{seed}", resume)
        train_elapsed = perf_counter() - started
        started = perf_counter()
        pred = fit.predict(history, actual.index)
        predict_elapsed = perf_counter() - started
        predictions.append(pred.to_numpy())
        training += train_elapsed
        inference += predict_elapsed
        seed_scores.extend({"seed": seed, "training_seconds": train_elapsed,
                            "inference_seconds": predict_elapsed, **row}
                           for row in score_sensor_forecast(actual, pred))
        pd.DataFrame(seed_scores).to_csv(directory / "metrics" / "tft_seed_scores.csv", index=False)
    return pd.DataFrame(np.mean(predictions, axis=0), index=actual.index, columns=targets), training, inference


def benchmark(models: list[str], subset: str, unit: int, targets: list[str], horizon: int,
              configs: dict[str, dict], tft_mode: str | None = None,
              resume: Path | None = None) -> Path:
    """Run configured fits, retain failures, and report only completed forecasts."""
    data_config = read_settings("data", "cmapss.yaml")
    frame = CMapssLoader(resolve_path(data_config["raw_dir"])).load_train(subset)
    history, test = split_history(frame, unit, targets, horizon)
    directory = new_run_directory()
    LOGGER.info("Writing benchmark to %s", directory)
    manifest = {"subset": subset.upper(), "source": "C-MAPSS train trajectories",
                "unit": unit, "targets": targets, "history_last_cycle": int(history.index[-1]),
                "test_cycles": test.index.tolist(), "models": models, "configs": configs,
                "tft_mode": tft_mode, "resume": str(resume) if resume else None}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    rows, attempts = [], []
    for model in dict.fromkeys(models):
        LOGGER.info("Starting %s", model)
        if model == "tft" and tft_mode is None:
            attempts.append({"model": model, "status": "skipped", "detail": "TFT requires explicit mode"})
            continue
        actual = test if model in MULTIVARIATE or model == "tft" else test.iloc[:, :1]
        model_targets = list(actual.columns)
        protocol = (tft_mode if model == "tft" else "local_engine_history")
        try:
            config = configs[model]
            diagnostics = {}
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                if model == "tft":
                    prediction, training, inference = _run_tft(
                        frame, unit, model_targets, history, actual, config, directory, resume)
                else:
                    columns = config.get("exog", [])
                    started = perf_counter()
                    fit = fit_statistical(model, history[model_targets], config,
                                          known_regressors(history.index, columns))
                    training = perf_counter() - started
                    started = perf_counter()
                    prediction = fit.predict(actual.index, known_regressors(actual.index, columns))
                    inference = perf_counter() - started
                    diagnostics = fit.diagnostics
                    fit.save(directory / f"{model}.pkl")
            metrics = score_sensor_forecast(actual, prediction)
            diagnostics["warnings"] = sorted({str(item.message) for item in caught})
            (directory / "metrics" / f"{model}_diagnostics.json").write_text(
                json.dumps(diagnostics, indent=2, allow_nan=False), encoding="utf-8")
            pd.concat({"actual": actual, "forecast": prediction}, axis=1).to_csv(
                directory / "metrics" / f"{model}_forecast.csv")
            model_figures(directory, model, history, actual, prediction)
            rows.extend({"model": model, "protocol": protocol, "training_seconds": training,
                         "inference_seconds": inference, **metric} for metric in metrics)
            attempts.append({"model": model, "status": "completed", "detail": ""})
        except ImportError as error:
            LOGGER.warning("%s: %s", model, error)
            attempts.append({"model": model, "status": "skipped", "detail": str(error)})
        except (ValueError, TypeError, RuntimeError, ArithmeticError, OSError, KeyError,
                np.linalg.LinAlgError) as error:
            LOGGER.error("%s: %s", model, error)
            attempts.append({"model": model, "status": "failed", "detail": str(error)})
    comparison_report(directory, rows, attempts)
    return directory


def main(argv: list[str] | None = None) -> int:
    """Parse model selections and run the benchmark from any working directory."""
    import yaml

    settings = read_settings("forecasting", "benchmark.yaml")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", required=True, choices=sorted(STATISTICAL | {"tft"}))
    parser.add_argument("--subset", default=settings["subset"])
    parser.add_argument("--unit", type=int, default=settings["unit"])
    parser.add_argument("--targets", nargs="+", default=settings["targets"])
    parser.add_argument("--horizon", type=int, default=settings["horizon"])
    parser.add_argument("--config", action="append", default=[], metavar="MODEL=YAML")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--tft-smoke", action="store_const", const="cpu_smoke", dest="tft_mode")
    mode.add_argument("--full-tft", action="store_const", const="global_engine_holdout", dest="tft_mode")
    parser.add_argument("--resume", type=Path, help="Path to a compatible TFT last.ckpt")
    args = parser.parse_args(argv)
    if args.resume and ("tft" not in args.models or not args.tft_mode):
        parser.error("--resume requires TFT and an explicit TFT mode")
    configs = {}
    for model in args.models:
        if model == "tft" and args.tft_mode is None:
            continue
        filename = "tft_smoke" if model == "tft" and args.tft_mode == "cpu_smoke" else model
        configs[model] = (settings["baselines"][model] if model in settings["baselines"]
                          else read_settings("models", f"{filename}.yaml"))
    for override in args.config:
        model, separator, path = override.partition("=")
        if not separator or model not in configs:
            parser.error("--config requires a selected MODEL=YAML")
        with resolve_path(path).open(encoding="utf-8") as stream:
            overrides = yaml.safe_load(stream)
        if not isinstance(overrides, dict):
            parser.error("--config file must contain a YAML mapping")
        configs[model] = configs[model] | overrides
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    directory = benchmark(args.models, args.subset, args.unit, args.targets, args.horizon, configs,
                          args.tft_mode, resolve_path(args.resume) if args.resume else None)
    print(directory)
    attempts = pd.read_csv(directory / "metrics" / "attempts.csv")
    return 0 if attempts["status"].eq("completed").all() else 1


if __name__ == "__main__":
    raise SystemExit(main())
