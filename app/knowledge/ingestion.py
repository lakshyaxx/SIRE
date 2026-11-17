"""Local attachment validation, page/line-aware extraction and deterministic chunks."""

import hashlib
from threading import Event
import io
import json
import re
import uuid
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.config import SETTINGS
from app.core.errors import SireError
from app.prediction.telemetry import ingest_csv
from app.storage.database import Store, now


def attachment_receipt(store: Store, item: dict, deduplicated: bool = False) -> dict:
    """Return the existing attachment contract plus durable, explicitly qualified intake provenance."""
    from app.evidence.ledger import Ledger

    metadata = dict(item["metadata"])
    if not metadata.get("evidence_ids"):
        resolved = Ledger(store).resolve(item["id"])
        metadata["evidence_ids"] = [resolved["evidence"]["id"]]
        metadata["evidence_source_ids"] = [resolved["source"]["id"]]
        with store.connection() as db:
            db.execute(
                "UPDATE attachments SET metadata=? WHERE id=?",
                (json.dumps(metadata), item["id"]),
            )
    public = {key: value for key, value in item.items() if key != "path"}
    public["metadata"] = metadata
    return {
        **public,
        "attachment_id": item["id"],
        "original_filename": item["name"],
        "detected_media_type": item["mime"],
        "size_bytes": metadata.get("size_bytes", Path(item["path"]).stat().st_size),
        "stored_at": item["created_at"],
        "ingestion_status": "failed" if metadata.get("media_error") else "ready",
        "evidence_source_ids": metadata["evidence_source_ids"],
        "evidence_ids": metadata["evidence_ids"],
        "warnings": metadata.get("warnings", []),
        "deduplicated": deduplicated,
        "provenance_scope": "Durable uploaded-file identity; not proof that model observations or a physical diagnosis are verified.",
    }


def clean_image(content: bytes) -> bytes:
    """Decode an actual supported image and discard EXIF and other source metadata."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if (
                    image.format not in {"JPEG", "PNG", "WEBP"}
                    or image.width * image.height > 16000000
                ):
                    raise ValueError("Image limits")
                image.load()
                normalized = Image.new("RGB", image.size)
                normalized.paste(image.convert("RGB"))
                normalized.thumbnail((1600, 1600))
                output = io.BytesIO()
                normalized.save(output, format="JPEG", quality=85)
                return output.getvalue()
    except (
        OSError,
        ValueError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise SireError(
            "invalid_image", "Invalid or oversized JPEG, PNG or WebP."
        ) from exc


def extract_document(content: bytes, suffix: str) -> list[tuple[str, str]]:
    """Extract real PDF pages or numbered text lines with bounded output."""
    if suffix in {".json", ".docx", ".xlsx"}:
        from app.evidence.formats import sections as parse_sections

        extracted = parse_sections(content, suffix)
        if sum(len(t) for _, t in extracted) > 500000:
            raise SireError("invalid_document", "Extracted text exceeds the limit.")
        return extracted
    sections = []
    try:
        if suffix == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise ValueError("Invalid PDF signature")
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted or len(reader.pages) > 40:
                raise ValueError("Encrypted PDF or page limit exceeded")
            for number, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                if len(text) > 100000:
                    raise ValueError("PDF text exceeds page limit")
                sections.append((f"page {number}", text))
        else:
            lines = content.decode("utf-8-sig").splitlines()
            for start in range(0, len(lines), 24):
                sections.append(
                    (
                        f"lines {start+1}-{min(start+24,len(lines))}",
                        "\n".join(lines[start : start + 24]),
                    )
                )
        if sum(len(text) for _, text in sections) > 500000:
            raise ValueError("Document text limit")
        if not any(text.strip() for _, text in sections):
            raise ValueError("No extractable text; OCR is not configured")
    except (UnicodeError, ValueError, PdfReadError, KeyError, OSError) as exc:
        raise SireError(
            "invalid_document",
            "Unreadable, encrypted, oversized or image-only document; text extraction failed.",
        ) from exc
    return sections


def ingest(
    store: Store,
    conversation_id: str | None,
    filename: str,
    content: bytes,
    declared_dataset: str | None = None,
    compatible: bool = False,
    media_request_id: str | None = None,
    cancel_event: Event | None = None,
) -> dict[str, Any]:
    """Store randomized local files only after validation; never interpret embedded instructions."""
    if cancel_event is not None and cancel_event.is_set():
        raise SireError("media_cancelled", "Media intake cancelled.", 409)
    if conversation_id:
        store.conversation(conversation_id)
    if not content or len(content) > SETTINGS["max_upload_bytes"]:
        raise SireError(
            "upload_too_large", "File is empty or exceeds the upload limit.", 413
        )
    name = (
        re.sub(r"[^\w. -]", "_", filename.replace("\\", "/").split("/")[-1])[:120]
        or "attachment"
    )
    suffix = Path(name).suffix.lower()
    original_sha = hashlib.sha256(content).hexdigest()
    existing = (
        store.rows(
            "SELECT * FROM attachments WHERE conversation_id=?", (conversation_id,)
        )
        if conversation_id
        else []
    )
    for previous in existing:
        previous["metadata"] = json.loads(previous["metadata"])
        meta = previous["metadata"]
        if (
            meta.get("original_sha256", previous["sha256"]) == original_sha
            and Path(previous["name"]).suffix.lower() == suffix
            and meta.get("declared_dataset") == declared_dataset
            and bool(meta.get("compatible_cmapss", False)) == compatible
            and not meta.get("media_error")
            and not meta.get("parent_attachment_id")
        ):
            result = attachment_receipt(store, previous, True)
            result["requested_filename"] = name
            return result
    if len(existing) >= 30:
        raise SireError(
            "attachment_limit",
            "This conversation has reached its attachment limit.",
            413,
        )
    stored_bytes = sum(Path(row["path"]).stat().st_size for row in existing)
    if stored_bytes + len(content) > SETTINGS["max_conversation_attachment_bytes"]:
        raise SireError(
            "attachment_storage_limit",
            "This conversation has reached its local attachment storage quota.",
            413,
        )
    extracted_frames = []
    sections: list[tuple[str, str]] = []
    metadata: dict[str, Any] = {
        "source_type": "real_uploaded",
        "source_authenticity": "unverified",
        "original_sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        content = clean_image(content)
        kind, mime, stored_suffix = "image", "image/jpeg", ".jpg"
        metadata["retention"] = (
            "Stored locally with conversation; delete conversation to remove."
        )
    elif suffix in {".pdf", ".txt", ".md", ".json", ".docx", ".xlsx"}:
        kind, mime, stored_suffix = (
            "document",
            {
                ".pdf": "application/pdf",
                ".json": "application/json",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }.get(suffix, "text/plain"),
            suffix,
        )
        sections = extract_document(content, suffix)
    elif suffix in {".mp4", ".mov", ".avi", ".webm", ".mkv"}:
        from app.media.video import validate_container
        from app.media.runtime import run as run_media, POLICY
        from tempfile import NamedTemporaryFile

        validate_container(content[:64], suffix)
        if (
            conversation_id
            and len(store.attachments(conversation_id)) + POLICY["max_video_frames"] + 1
            > 30
        ):
            raise SireError(
                "attachment_limit",
                "Not enough attachment slots for bounded video frames; use a new conversation.",
                413,
            )
        kind, mime, stored_suffix = (
            "video",
            {
                ".mp4": "video/mp4",
                ".mov": "video/quicktime",
                ".avi": "video/x-msvideo",
                ".webm": "video/webm",
                ".mkv": "video/x-matroska",
            }[suffix],
            suffix,
        )
        directory = store.path.parent / "media_inputs"
        directory.mkdir(exist_ok=True)
        with NamedTemporaryFile(
            dir=directory, suffix=suffix, delete=False
        ) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name).resolve()
        if not temporary_path.is_relative_to(directory.resolve()):
            raise ValueError("Video input leaves private state")
        try:
            result = run_media("video", {"path": str(temporary_path)}, media_request_id)
            extracted_frames = result.pop("frames")
            metadata["video"] = {
                **result,
                "frames": [
                    {key: value for key, value in frame.items() if key != "image_bytes"}
                    for frame in extracted_frames
                ],
            }
        except SireError as exc:
            metadata["media_error"] = {"code": exc.code, "message": exc.message}
        finally:
            temporary_path.unlink(missing_ok=True)
    elif suffix in {".wav", ".flac", ".ogg", ".mp3"}:
        from app.voice.capabilities import inspect_wav
        from app.voice.service import transcribe_bytes, validate_audio

        kind, mime, stored_suffix = (
            "audio",
            {
                ".wav": "audio/wav",
                ".flac": "audio/flac",
                ".ogg": "audio/ogg",
                ".mp3": "audio/mpeg",
            }[suffix],
            suffix,
        )
        validate_audio(content, suffix)
        if suffix == ".wav":
            metadata["audio"] = inspect_wav(content)
        try:
            transcript = transcribe_bytes(
                content, media_request_id, suffix, cancel_event=cancel_event
            )
            metadata["transcript"] = transcript
            sections = [
                (
                    f"automatic transcript; recording 0-{transcript['duration_seconds']} seconds; alignment unavailable",
                    transcript["text"],
                )
            ]
        except SireError as exc:
            metadata["media_error"] = {"code": exc.code, "message": exc.message}
            metadata["transcription_status"] = "failed_or_unavailable"
    elif suffix == ".csv":
        kind, mime, stored_suffix = "csv", "text/csv", suffix
        parsed = ingest_csv(content, declared_dataset, compatible)
        metadata = {
            k: v for k, v in parsed.items() if k not in {"records", "upload_id"}
        }
        metadata.update(
            {"declared_dataset": declared_dataset, "compatible_cmapss": compatible}
        )
    else:
        raise SireError(
            "unsupported_type",
            "Supported attachments: images, PDF/TXT/MD/JSON/DOCX/XLSX/CSV, PCM WAV and bounded MP4/MOV/AVI/WebM/MKV.",
        )
    if suffix in {".csv", ".json"}:
        from app.evidence.measurements import parse as parse_measurements

        measurements = parse_measurements(content, suffix)
        if measurements:
            canonical = [
                {
                    key: row[key]
                    for key in [
                        "asset_id",
                        "channel",
                        "observed_at",
                        "value",
                        "unit",
                        "quality",
                    ]
                }
                for row in measurements
            ]
            canonical.sort(
                key=lambda row: (row["asset_id"], row["channel"], row["observed_at"])
            )
            metadata["measurement_content_sha256"] = hashlib.sha256(
                json.dumps(
                    canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                ).encode()
            ).hexdigest()
            metadata["measurement_schema"] = {
                "rows": len(measurements),
                "asset_ids": sorted({row["asset_id"] for row in measurements}),
                "units": sorted({row["unit"] for row in measurements}),
                "association": "user_declared_unverified",
            }
    metadata.setdefault("source_type", "real_uploaded")
    metadata.setdefault("source_authenticity", "unverified")
    metadata.setdefault("original_sha256", hashlib.sha256(content).hexdigest())
    metadata.setdefault("size_bytes", len(content))
    if cancel_event is not None and cancel_event.is_set():
        raise SireError(
            "media_cancelled", "Media intake cancelled before storage.", 409
        )
    identifier = uuid.uuid4().hex
    directory = store.path.parent / "attachments"
    directory.mkdir(exist_ok=True)
    path = directory / (identifier + stored_suffix)
    with path.open("xb") as target:
        target.write(content)
    digest = hashlib.sha256(content).hexdigest()
    chunks = []
    for locator, text in sections:
        for offset in range(0, len(text), 1200):
            excerpt = text[offset : offset + 1200]
            if excerpt.strip():
                chunk_id = hashlib.sha256(
                    f"{identifier}:{locator}:{offset}:{excerpt}".encode()
                ).hexdigest()[:24]
                chunks.append(
                    (
                        chunk_id,
                        identifier,
                        conversation_id,
                        f"{locator}, chars {offset+1}-{offset+len(excerpt)}",
                        excerpt,
                    )
                )
    try:
        with store.connection() as db:
            db.execute(
                "INSERT INTO attachments VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    conversation_id,
                    name,
                    kind,
                    mime,
                    digest,
                    str(path),
                    json.dumps(metadata),
                    now(),
                ),
            )
            db.executemany("INSERT INTO chunks VALUES(?,?,?,?,?)", chunks)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    if extracted_frames:
        for index, frame in enumerate(extracted_frames):
            child = ingest(
                store,
                conversation_id,
                f"{name} frame-{frame['frame_number']}.jpg",
                frame["image_bytes"],
            )
            child_metadata = dict(
                child["metadata"],
                parent_attachment_id=identifier,
                video_frame_number=frame["frame_number"],
                video_timestamp_seconds=frame["timestamp_seconds"],
                extraction_method="bounded_real_video_frame",
            )
            with store.connection() as db:
                db.execute(
                    "UPDATE attachments SET metadata=? WHERE id=?",
                    (json.dumps(child_metadata), child["id"]),
                )
            metadata["video"]["frames"][index].update(
                attachment_id=child["id"],
                decoder_jpeg_sha256=frame["sha256"],
                sha256=child["sha256"],
            )
        with store.connection() as db:
            db.execute(
                "UPDATE attachments SET metadata=? WHERE id=?",
                (json.dumps(metadata), identifier),
            )
    return attachment_receipt(store, store.attachment(identifier))


def csv_history(store: Store, identifier: str, dataset: str) -> pd.DataFrame:
    """Revalidate a persisted CSV for independent prediction; no implicit domain mapping."""
    from app.prediction.telemetry import validate_history

    item = store.attachment(identifier)
    meta = item["metadata"]
    if (
        item["kind"] != "csv"
        or not meta.get("prediction_eligible")
        or meta.get("declared_dataset") != dataset
    ):
        raise SireError(
            "incompatible_upload",
            "CSV lacks compatible C-MAPSS schema and dataset declaration.",
        )
    return validate_history(pd.read_csv(item["path"]))
