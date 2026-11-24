"""Bounded prediction-only NASA intake, preserving original bytes and engine identity."""

import csv
import hashlib
import io
import json
import re
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.config import SETTINGS
from app.core.errors import SireError
from app.prediction.telemetry import DATASETS, RAW_COLUMNS, validate_history
from app.storage.database import Store, now


def column_name(value: str) -> str:
    """Map explicit NASA aliases; never guess a generic industrial channel."""
    name = re.sub(r"[\s_-]+", "", value.strip().lower())
    if name in {"unit", "unitid", "engine", "engineid", "unitnumber"}:
        return "unit"
    if name in {"cycle", "cycles", "timecycle"}:
        return "cycle"
    match = re.fullmatch(r"(?:op|setting|operationalsetting)([1-3])", name)
    if match:
        return "op" + match[1]
    match = re.fullmatch(r"(?:s|sensor)(\d{1,2})", name)
    return "s" + str(int(match[1])) if match else name


def parse(content: bytes, filename: str) -> pd.DataFrame:
    """Read every bounded row; reject malformed, missing, duplicate or reordered cycles."""
    if not content or len(content) > SETTINGS["max_upload_bytes"]:
        raise SireError(
            "upload_too_large", "Empty file or prediction upload exceeds 10 MB.", 413
        )
    suffix = Path(filename).suffix.lower()
    if suffix not in {".txt", ".csv"}:
        raise SireError(
            "prediction_format", "Use original NASA TXT or a headered NASA CSV."
        )
    try:
        text = content.decode("utf-8-sig")
        if "\x00" in text:
            raise ValueError("Binary data is not supported")
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines or len(lines) > 100001:
            raise ValueError("Use at most 100,000 observations")
        delimiter = next((d for d in [",", ";", "\t"] if d in lines[0]), None)
        if suffix == ".txt" and not any(d in lines[0] for d in [",", ";"]):
            rows = [line.split() for line in lines]
            header = list(RAW_COLUMNS)
        else:
            if delimiter is None:
                raise ValueError("CSV needs named, delimited columns")
            parsed = list(
                csv.reader(io.StringIO(text), delimiter=delimiter, strict=True)
            )
            header = [column_name(name) for name in parsed[0]]
            rows = [row for row in parsed[1:] if row]
        if len(header) != 26 or set(header) != set(RAW_COLUMNS):
            raise ValueError(
                "Expected unit, cycle, op1-op3 and s1-s21; RUL label files are not histories"
            )
        if len(rows) > 100000:
            raise ValueError("Use at most 100,000 observations")
        if not rows or any(len(row) != 26 for row in rows):
            raise ValueError("Every observation must contain exactly 26 values")
        frame = pd.DataFrame(rows, columns=header).loc[:, RAW_COLUMNS].astype(float)
        values = frame.to_numpy()
        if not np.isfinite(values).all():
            raise ValueError("Missing, NaN and infinite values are refused")
        for _, group in frame.groupby("unit", sort=False):
            validate_history(group)
        return frame
    except (UnicodeError, ValueError, csv.Error, SireError) as exc:
        message = exc.message if isinstance(exc, SireError) else str(exc)
        raise SireError("invalid_prediction_data", message) from exc


def summary(frame: pd.DataFrame) -> dict:
    """Compute full-file statistics independently of the limited preview."""
    engines = [
        {
            "unit_id": int(unit),
            "rows": len(group),
            "first_cycle": int(group.cycle.min()),
            "last_cycle": int(group.cycle.max()),
        }
        for unit, group in frame.groupby("unit", sort=True)
    ]
    return {
        "rows": len(frame),
        "columns": list(RAW_COLUMNS),
        "engine_count": len(engines),
        "engines": engines,
        "missing_values": 0,
        "duplicate_cycles": 0,
        "preview_rows": min(5, len(frame)),
        "preview": frame.head(5).to_dict("records"),
        "preview_scope": "First five rows only; row and engine counts cover the full file.",
    }


def ingest(
    store: Store,
    conversation_id: str | None,
    filename: str,
    content: bytes,
    dataset: str,
    compatible: bool,
) -> dict:
    """Persist validated prediction input in existing attachment storage, without schema changes."""
    from app.knowledge.ingestion import attachment_receipt

    if dataset not in DATASETS:
        raise SireError("unknown_dataset", "Select FD001-FD004 explicitly.")
    if conversation_id:
        store.conversation(conversation_id)
    frame = parse(content, filename)
    existing = (
        store.rows(
            "SELECT path FROM attachments WHERE conversation_id=?", (conversation_id,)
        )
        if conversation_id
        else []
    )
    if (
        len(existing) >= 30
        or sum(Path(row["path"]).stat().st_size for row in existing) + len(content)
        > SETTINGS["max_conversation_attachment_bytes"]
    ):
        raise SireError(
            "attachment_storage_limit", "Conversation attachment quota reached.", 413
        )
    name = re.sub(r"[^\w. -]", "_", filename.replace("\\", "/").split("/")[-1])[:120]
    identifier = uuid.uuid4().hex
    directory = store.path.parent / "attachments"
    directory.mkdir(exist_ok=True)
    path = directory / (identifier + Path(name).suffix.lower())
    sha = hashlib.sha256(content).hexdigest()
    meta = {
        **summary(frame),
        "prediction_dataset": True,
        "prediction_eligible": compatible,
        "declared_dataset": dataset,
        "compatible_cmapss": compatible,
        "original_sha256": sha,
        "size_bytes": len(content),
        "provenance": "User-declared NASA simulation; schema validation does not authenticate origin.",
        "warnings": (
            []
            if compatible
            else [
                "Confirm this file is C-MAPSS simulation data for the selected subset before predicting."
            ]
        ),
    }
    with path.open("xb") as target:
        target.write(content)
    try:
        with store.connection() as db:
            db.execute(
                "INSERT INTO attachments VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    conversation_id,
                    name,
                    "csv",
                    "text/plain" if path.suffix == ".txt" else "text/csv",
                    sha,
                    str(path),
                    json.dumps(meta),
                    now(),
                ),
            )
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return attachment_receipt(store, store.attachment(identifier))


def history(
    store: Store, identifier: str, dataset: str, unit_id: int | None = None
) -> pd.DataFrame:
    """Resolve a persisted input and require explicit engine choice for multi-engine files."""
    item = store.attachment(identifier)
    meta = item["metadata"]
    if not meta.get("prediction_dataset"):
        from app.knowledge.ingestion import csv_history
        from app.evidence.integrity import read_verified

        read_verified(item)
        frame = csv_history(store, identifier, dataset)
    else:
        if (
            not meta.get("prediction_eligible")
            or meta.get("declared_dataset") != dataset
        ):
            raise SireError(
                "incompatible_upload",
                "Declare matching NASA subset and compatibility before predicting.",
            )
        content = Path(item["path"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise SireError(
                "input_integrity",
                "Uploaded input bytes changed; upload the original again.",
            )
        frame = parse(content, item["name"])
    units = frame.unit.unique()
    if unit_id is None:
        if len(units) != 1:
            raise SireError(
                "engine_required",
                "Select an engine/unit from this multi-engine dataset.",
            )
        unit_id = int(units[0])
    selected = frame.loc[frame.unit.eq(unit_id)].copy()
    if selected.empty:
        raise SireError(
            "unknown_engine",
            f"Engine/unit {unit_id} is not present in this uploaded dataset.",
        )
    return validate_history(selected)
