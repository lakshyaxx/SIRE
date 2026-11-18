"""Compare fresh one-shot and resident LightGBM predictions on real NASA inputs."""

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import median
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.prediction import hub, telemetry
from app.prediction.policy import default_model
from app.core.errors import SireError


def main() -> None:
    """Report every sample and require exact output parity across both paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=telemetry.DATASETS, action="append")
    parser.add_argument("--runs", type=int, default=4)
    args = parser.parse_args()
    if args.runs < 2:
        parser.error("--runs must be at least two")

    # Preflight without starting a worker or writing to production state.
    try:
        hub.verify_integrity()
    except SireError as exc:
        raise SystemExit(
            f"Native benchmark cannot start ({exc.code}): {exc.message} "
            "Restore the checksummed private runtime described in README.md."
        ) from exc
    regressions = []
    for dataset in args.dataset or telemetry.DATASETS:
        model_id = default_model(dataset)["model_id"]
        ids = [row["asset_id"] for row in telemetry.assets(dataset)[: args.runs]]
        if len(ids) != args.runs:
            parser.error(f"{dataset} has fewer than {args.runs} engine histories")
        histories = [telemetry.asset_history(identifier, dataset) for identifier in ids]
        samples: dict[str, list[float]] = {"one_shot": [], "resident": []}
        previous = os.environ.get("SIRE_WARM_PREDICTION")
        try:
            for label in samples:
                hub.WARM_WORKER.close()
                os.environ["SIRE_WARM_PREDICTION"] = "1" if label == "resident" else "0"
                outputs = []
                for history in histories:
                    started = perf_counter()
                    outputs.append(hub.predict(model_id, dataset, history))
                    samples[label].append(perf_counter() - started)
                if label == "one_shot":
                    baseline = outputs
                elif outputs != baseline:
                    raise SystemExit(f"{model_id}: native prediction outputs differ")
                elif hub.WARM_WORKER.snapshot()["requests"] != args.runs:
                    raise SystemExit(f"{model_id}: resident reuse was not observed")
        finally:
            hub.WARM_WORKER.close()
            if previous is None:
                os.environ.pop("SIRE_WARM_PREDICTION", None)
            else:
                os.environ["SIRE_WARM_PREDICTION"] = previous
        cold_resident, *warm = samples["resident"]
        paired_one_shot = samples["one_shot"][1:]
        paired_savings = [
            baseline_seconds - warm_seconds
            for baseline_seconds, warm_seconds in zip(
                paired_one_shot, warm, strict=True
            )
        ]
        median_savings = median(paired_savings)
        if median_savings <= 0:
            regressions.append(model_id)
        print(
            json.dumps(
                {
                    "dataset": dataset,
                    "model_id": model_id,
                    "asset_ids": ids,
                    "exact_output_parity": True,
                    "seconds": samples,
                    "cold_resident_seconds": cold_resident,
                    "paired_one_shot_median_seconds": median(paired_one_shot),
                    "warm_median_seconds": median(warm),
                    "paired_median_savings_seconds": median_savings,
                }
            ),
            flush=True,
        )
    if regressions:
        raise SystemExit("No positive median savings for: " + ", ".join(regressions))


if __name__ == "__main__":
    main()
