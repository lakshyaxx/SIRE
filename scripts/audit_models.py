"""Verify every consolidated catalog entry with actual source-backed inference."""

import json
import sys
import time
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.prediction.hub import manifest, predict, verify_integrity
from app.prediction.telemetry import asset_history


def audit(only_missing: bool = False, output_path: Path | None = None) -> dict:
    """Save fresh outputs and compare primary routes to independently run V1 outputs."""
    target = output_path or ROOT / "ml/registry/verification.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads((ROOT / "ml/registry/v1_reference.json").read_text())
    results = (
        json.loads(target.read_text()) if only_missing and target.is_file() else {}
    )
    print("INTEGRITY", verify_integrity(), flush=True)
    for item in manifest()["models"]:
        start = time.monotonic()
        identifier = item["model_id"]
        if only_missing and results.get(identifier, {}).get("status") == "ready":
            continue
        try:
            out = predict(
                identifier,
                item["dataset"],
                asset_history(f"{item['dataset']}-ENGINE-001", item["dataset"]),
                item["task"],
            )
            parity = None
            if identifier in old:
                key = "anomaly_score" if item["task"] == "anomaly" else "rul"
                delta = abs(float(out[key]) - float(old[identifier]["output"][key]))
                if delta > 1e-8:
                    raise ValueError(
                        f"Original/consolidated parity difference: {delta}"
                    )
                parity = {
                    "absolute_difference": delta,
                    "tolerance": 1e-8,
                    "source": "Fresh V1 audit before cutover",
                }
            results[identifier] = {
                "status": "ready",
                "stage": "INFERRED",
                "output": out,
                "parity": parity,
                "elapsed_seconds": time.monotonic() - start,
                "runtime": "cpu",
            }
        except Exception as exc:
            results[identifier] = {
                "status": "unavailable",
                "stage": "ERROR",
                "error": str(exc),
                "elapsed_seconds": time.monotonic() - start,
            }
        pending = target.with_suffix(".pending.json")
        pending.write_text(json.dumps(results, indent=2), encoding="utf-8")
        pending.replace(target)
        print(
            identifier,
            results[identifier]["stage"],
            round(time.monotonic() - start, 2),
            flush=True,
        )
    print(
        "RESULTS",
        {
            s: sum(v["status"] == s for v in results.values())
            for s in ["ready", "unavailable"]
        },
        flush=True,
    )
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--missing", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = audit(only_missing=args.missing, output_path=args.output)
    raise SystemExit(1 if any(r["status"] != "ready" for r in results.values()) else 0)
