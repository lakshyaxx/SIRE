"""Immutable artifact catalog and bounded, isolated legacy inference."""

import hashlib
import importlib.util
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from threading import BoundedSemaphore, Event
from typing import Any

import pandas as pd

from app.core.config import MANIFEST, ROOT, SETTINGS
from app.core.errors import SireError
from app.providers.resources import SCHEDULER
from app.core.worker_pool import terminate_owned
from app.prediction.telemetry import validate_history

LOGGER = logging.getLogger(__name__)
INFERENCE_LOCK = BoundedSemaphore(1)


def manifest() -> dict[str, Any]:
    """Read the generated catalog, which contains paths only from local discovery."""
    if not MANIFEST.is_file():
        raise SireError(
            "catalog_unavailable",
            "Restore the verified ml/registry/catalog.json from the private runtime bundle.",
            503,
        )
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def catalog() -> list[dict[str, Any]]:
    """Expose discovered entries with independently recorded smoke-test status."""
    data = manifest()
    checks_path = ROOT / "ml/registry/verification.json"
    checks = json.loads(checks_path.read_text()) if checks_path.is_file() else {}
    local_path = ROOT / ".runtime/prediction-model-verification.json"
    local_checks = (
        json.loads(local_path.read_text(encoding="utf-8"))
        if local_path.is_file()
        else {}
    )
    result = []
    for item in data["models"]:
        record = dict(item)
        record["verification"] = checks.get(item["model_id"], {"status": "not_tested"})
        record["status"] = record["verification"]["status"]
        record["runnable_status"] = record["status"]
        record["error_details"] = record["verification"].get("error")
        from app.core.config import TRACK

        required = [
            TRACK / item["artifact_dir"],
            TRACK / item["predict_module"],
            TRACK / "artifacts/common" / item["dataset"] / "preprocessor.joblib",
        ]
        required.extend(ROOT / path for path in item.get("weight_paths", []))
        required.extend(ROOT / path for path in item.get("calibration_paths", []))
        missing = [
            path.relative_to(ROOT).as_posix() for path in required if not path.exists()
        ]
        dependencies = ["lightgbm", "sklearn", "torch", "joblib"]
        unavailable = [
            name for name in dependencies if importlib.util.find_spec(name) is None
        ]
        record["availability"] = "available_not_locally_verified"
        if missing or unavailable:
            preprocessor = (
                TRACK / "artifacts/common" / item["dataset"] / "preprocessor.joblib"
            )
            record["status"] = (
                "preprocessing_missing"
                if not preprocessor.is_file()
                else "artifact_missing" if missing else "dependency_unavailable"
            )
            record["error_details"] = {
                "missing_paths": missing,
                "missing_dependencies": unavailable,
            }
            record["runnable_status"] = record["status"]
            record["availability"] = record["status"]
        if local_checks:
            local = local_checks.get(item["model_id"], {})
            record["local_verification"] = local
            if not missing and not unavailable and local.get("status") == "ready":
                record["availability"] = "inference_verified_locally"
            elif local.get("status") == "unavailable":
                parity_mismatch = str(local.get("error", "")).startswith(
                    "Original/consolidated parity difference:"
                )
                if parity_mismatch and not missing and not unavailable:
                    record["availability"] = (
                        "inference_executed_historical_parity_mismatch"
                    )
                    record["local_parity"] = "failed"
                else:
                    record["status"] = "loading_failed"
                    record["runnable_status"] = "loading_failed"
                    record["availability"] = "loading_failed"
                record["error_details"] = local.get("error")
        record["version"] = (
            record["verification"]
            .get("output", {})
            .get("version", record.get("version"))
        )
        result.append(record)
    return result


def entry(model_id: str) -> dict[str, Any]:
    """Resolve an opaque catalog ID rather than accepting client-supplied paths."""
    for item in manifest()["models"]:
        if item["model_id"] == model_id:
            return item
    raise SireError("unknown_model", "Unknown model ID.", 404)


def verify_integrity() -> int:
    """Check all captured inference files against the pre-migration byte manifest."""
    records = manifest()["integrity_files"]
    for record in records:
        path = ROOT / record["path"]
        if not path.is_file():
            raise SireError(
                "artifact_missing", "A preserved inference dependency is missing.", 503
            )
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != record["sha256"]:
            raise SireError(
                "artifact_integrity", "Preserved inference bytes have changed.", 503
            )
    return len(records)


def predict(
    model_id: str,
    dataset: str,
    history: pd.DataFrame,
    task: str = "rul",
    cancel_event: Event | None = None,
) -> dict[str, Any]:
    """Execute original prediction in a serial CPU process with a hard timeout."""
    with SCHEDULER.lease("native_rul", model=model_id, cancelled=cancel_event):
        selected = entry(model_id)
        if selected["dataset"] != dataset:
            raise SireError("dataset_mismatch", "Model and history datasets differ.")
        if selected["task"] != task:
            raise SireError(
                "task_mismatch", "Anomaly scores and RUL estimates use separate tools."
            )
        history = validate_history(history)
        if not INFERENCE_LOCK.acquire(blocking=False):
            raise SireError(
                "inference_busy", "Another prediction is running; retry shortly.", 429
            )
        process = None
        input_stream = None
        try:
            if cancel_event is not None and cancel_event.is_set():
                raise SireError(
                    "inference_cancelled",
                    "Native inference cancelled before execution.",
                    409,
                )
            env = dict(
                os.environ,
                PYTHONDONTWRITEBYTECODE="1",
                CUDA_VISIBLE_DEVICES="",
                OMP_NUM_THREADS="2",
                OPENBLAS_NUM_THREADS="2",
                MPLCONFIGDIR=str(ROOT / ".runtime/matplotlib"),
            )
            began = time.monotonic()
            # Windows communicate(input=...) writes synchronously before its timeout.
            # A worker importing a model may not yet read a pipe; a private seekable
            # input stream keeps Stop/deadline polling independent of that read.
            input_directory = ROOT / ".runtime/inference_inputs"
            input_directory.mkdir(parents=True, exist_ok=True)
            input_stream = tempfile.TemporaryFile(mode="w+b", dir=input_directory)
            input_stream.write(
                json.dumps(
                    {"model_id": model_id, "history": history.to_dict("records")}
                ).encode("utf-8")
            )
            input_stream.seek(0)
            process = subprocess.Popen(
                [sys.executable, "-m", "app.prediction.worker"],
                cwd=ROOT,
                env=env,
                stdin=input_stream,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise SireError(
                        "inference_cancelled",
                        "Native inference cancelled; no prediction was substituted.",
                        409,
                    )
                if time.monotonic() - began > SETTINGS["worker_timeout_seconds"]:
                    raise subprocess.TimeoutExpired(
                        process.args, SETTINGS["worker_timeout_seconds"]
                    )
                try:
                    stdout, stderr = process.communicate(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    continue
            result = subprocess.CompletedProcess(
                process.args, process.returncode, stdout, stderr
            )
            if result.returncode:
                LOGGER.error(
                    "Model worker failed for %s (exit %s)", model_id, result.returncode
                )
                raise SireError(
                    "model_unavailable",
                    "Saved predictor could not run; see local verification results.",
                    503,
                )
            marker = "SIRE_RESULT="
            line = next(
                (
                    line
                    for line in reversed(result.stdout.splitlines())
                    if line.startswith(marker)
                ),
                None,
            )
            if line is None:
                raise SireError(
                    "model_unavailable", "Predictor returned no valid result.", 503
                )
            return json.loads(line[len(marker) :])
        except subprocess.TimeoutExpired as exc:
            raise SireError(
                "inference_timeout", "Prediction exceeded the configured timeout.", 503
            ) from exc
        finally:
            try:
                if process is not None and process.poll() is None:
                    terminate_owned(process)
                    process.communicate(timeout=5)
            finally:
                try:
                    if input_stream is not None:
                        input_stream.close()
                finally:
                    INFERENCE_LOCK.release()
