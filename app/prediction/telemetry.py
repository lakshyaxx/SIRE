"""Strict C-MAPSS ingestion and source-backed NASA demonstration assets."""

import csv
import io
import re
import time
import uuid
from functools import lru_cache
from threading import RLock
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import SETTINGS, TRACK
from app.core.errors import SireError

DATASETS = ("FD001", "FD002", "FD003", "FD004")
RAW_COLUMNS = ("unit", "cycle", "op1", "op2", "op3", *(f"s{i}" for i in range(1, 22)))
ORIGIN = "nasa_cmapss_simulation"
UPLOADS: dict[str, tuple[float, pd.DataFrame, str | None, bool]] = {}
UPLOAD_LOCK = RLock()


def validate_history(frame: pd.DataFrame) -> pd.DataFrame:
    """Require one complete, finite, ordered raw engine history without coercion."""
    if frame.empty or len(frame) > SETTINGS["max_history_rows"]:
        raise SireError("invalid_history", "History is empty or exceeds the row limit.")
    if set(frame.columns) != set(RAW_COLUMNS) or len(frame.columns) != len(RAW_COLUMNS):
        raise SireError(
            "invalid_schema", "Expected unit, cycle, op1-op3 and s1-s21 exactly."
        )
    try:
        values = frame.loc[:, RAW_COLUMNS].to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise SireError(
            "invalid_history", "Every C-MAPSS field must be numeric."
        ) from exc
    if not np.isfinite(values).all():
        raise SireError(
            "invalid_history", "Missing, NaN and infinite values are refused."
        )
    ids, cycles = values[:, 0], values[:, 1]
    if (
        len(np.unique(ids)) != 1
        or np.any(ids < 1)
        or np.any(ids != np.floor(ids))
        or np.any(cycles < 1)
        or np.any(cycles != np.floor(cycles))
        or np.any(np.diff(cycles) != 1)
    ):
        raise SireError(
            "invalid_history", "Use one engine with contiguous, ordered integer cycles."
        )
    return pd.DataFrame(values, columns=RAW_COLUMNS)


@lru_cache(maxsize=4)
def dataset_frame(dataset: str) -> pd.DataFrame:
    """Read real official test sensor histories; never read test RUL labels."""
    if dataset not in DATASETS:
        raise SireError("unknown_dataset", "Unsupported dataset.", 404)
    path = TRACK / "data" / f"test_{dataset}.txt"
    if not path.is_file():
        raise SireError("data_unavailable", "NASA demonstration data is missing.", 503)
    frame = pd.read_csv(path, sep=r"\s+", header=None)
    if frame.shape[1] != len(RAW_COLUMNS):
        raise SireError(
            "invalid_source",
            "NASA source schema differs from the expected 26 fields.",
            503,
        )
    frame.columns = RAW_COLUMNS
    return frame


def assets(dataset: str) -> list[dict[str, Any]]:
    """Derive engine IDs and cycle counts from the source file."""
    frame = dataset_frame(dataset)
    return [
        {
            "asset_id": f"{dataset}-ENGINE-{int(unit):03d}",
            "display_name": f"{dataset} / Engine {int(unit):03d}",
            "asset_type": "simulated_turbofan_engine",
            "dataset": dataset,
            "data_origin": ORIGIN,
            "last_cycle": int(group.cycle.max()),
            "rows": len(group),
        }
        for unit, group in frame.groupby("unit", sort=True)
    ]


def asset_history(asset_id: str, dataset: str) -> pd.DataFrame:
    """Resolve a strict public asset identifier, never an arbitrary file path."""
    match = re.fullmatch(r"(FD00[1-4])-ENGINE-(\d{3})", asset_id)
    if match is None:
        raise SireError("unknown_asset", "Unknown demonstration asset.", 404)
    if match[1] != dataset:
        raise SireError("dataset_mismatch", "Asset and model datasets differ.")
    frame = dataset_frame(dataset)
    return validate_history(frame.loc[frame.unit.eq(int(match[2]))].copy())


def telemetry(asset_id: str, dataset: str) -> dict[str, Any]:
    """Return raw readings and provenance; sensor physical units are not inferred."""
    frame = asset_history(asset_id, dataset)
    return {
        "asset_id": asset_id,
        "dataset": dataset,
        "data_origin": ORIGIN,
        "unit": "operating_cycle",
        "sensor_keys": list(RAW_COLUMNS[5:]),
        "source": f"ml/artifacts/cmapss/data/test_{dataset}.txt",
        "records": frame.to_dict(orient="records"),
    }


def ingest_csv(content: bytes, dataset: str | None, compatible: bool) -> dict[str, Any]:
    """Preview bounded UTF-8 CSV; require declared domain compatibility to predict."""
    if len(content) > SETTINGS["max_upload_bytes"]:
        raise SireError("upload_too_large", "CSV exceeds the upload limit.", 413)
    if dataset is not None and dataset not in DATASETS:
        raise SireError("unknown_dataset", "Unsupported declared dataset.")
    try:
        text = content.decode("utf-8-sig")
        if "\x00" in text:
            raise ValueError("Binary content is not CSV")
        header = next(iter(csv.reader(io.StringIO(text))))
        if len(header) > 100 or len(set(header)) != len(header):
            raise ValueError("Invalid columns")
        for index, row in enumerate(csv.reader(io.StringIO(text), strict=True)):
            if index > SETTINGS["max_history_rows"] or row and len(row) != len(header):
                raise ValueError("CSV row width or row budget mismatch")
        frame = pd.read_csv(io.StringIO(text), nrows=SETTINGS["max_history_rows"] + 1)
        if frame.empty or len(frame) > SETTINGS["max_history_rows"]:
            raise ValueError("Invalid rows")
    except (
        UnicodeError,
        ValueError,
        StopIteration,
        csv.Error,
        pd.errors.ParserError,
    ) as exc:
        raise SireError(
            "invalid_csv", "Use a nonempty bounded UTF-8 CSV with unique headers."
        ) from exc
    warnings = []
    try:
        frame = validate_history(frame)
        schema_ok = True
    except SireError as exc:
        schema_ok = False
        warnings.append(exc.message)
    eligible = schema_ok and dataset is not None and compatible
    if not eligible:
        warnings.append(
            "Prediction requires exact C-MAPSS schema, a dataset and confirmed compatible NASA simulation data."
        )
    identifier = uuid.uuid4().hex
    with UPLOAD_LOCK:
        now = time.monotonic()
        for key in list(UPLOADS):
            if now - UPLOADS[key][0] > SETTINGS["upload_retention_seconds"]:
                del UPLOADS[key]
        while len(UPLOADS) >= SETTINGS["max_uploads"]:
            del UPLOADS[next(iter(UPLOADS))]
        UPLOADS[identifier] = (now, frame, dataset, eligible)
    preview = frame.head(5).astype(object).where(pd.notna(frame.head(5)), None)
    preview = preview.replace([np.inf, -np.inf], None)
    return {
        "upload_id": identifier,
        "rows": len(frame),
        "columns": list(frame.columns),
        "prediction_eligible": eligible,
        "records": frame.to_dict("records") if eligible else None,
        "preview": preview.to_dict("records"),
        "warnings": warnings,
    }


def upload_history(identifier: str, dataset: str) -> pd.DataFrame:
    """Read a short-lived in-memory upload only if it passed prediction validation."""
    with UPLOAD_LOCK:
        item = UPLOADS.get(identifier)
        if (
            item is None
            or time.monotonic() - item[0] > SETTINGS["upload_retention_seconds"]
        ):
            UPLOADS.pop(identifier, None)
            raise SireError(
                "upload_expired", "Upload missing or expired; upload again.", 404
            )
        _, frame, declared, eligible = item
        if not eligible or declared != dataset:
            raise SireError(
                "incompatible_upload", "Upload is not eligible for this model dataset."
            )
        return validate_history(frame)
