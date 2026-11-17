"""Canonical private upload snapshots, original byte identity and safe parser locators."""

import hashlib
import re
from pathlib import Path
from app.core.config import SETTINGS
from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.evidence.formats import sections
from app.knowledge.ingestion import extract_document, clean_image
from app.voice.capabilities import inspect_wav


def ingest(ledger: Ledger, filename: str, content: bytes) -> dict:
    """Retain originals privately after validation; no file content can become tool instructions."""
    if not content or len(content) > SETTINGS["max_upload_bytes"]:
        raise SireError("upload_too_large", "Empty or oversized upload.", 413)
    name = re.sub(r"[^\w. -]", "_", filename.replace("\\", "/").split("/")[-1])[:120]
    suffix = Path(name).suffix.lower()
    mime = {
        ".json": "application/json",
        ".csv": "text/csv",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(suffix, "application/octet-stream")
    if suffix in {".json", ".csv", ".docx", ".xlsx"}:
        parsed = sections(content, suffix)
    elif suffix in {".txt", ".md", ".pdf"}:
        parsed = extract_document(content, suffix)
    elif suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        clean_image(content)
        parsed = [
            ("image bytes", "Validated image; vision inference has not been requested.")
        ]
        mime = "image/" + ("jpeg" if suffix in {".jpg", ".jpeg"} else suffix[1:])
    elif suffix == ".wav":
        parsed = [("audio metadata", str(inspect_wav(content)))]
        mime = "audio/wav"
    else:
        raise SireError(
            "unsupported_format",
            "Unsupported format; video/audio codecs or local speech models are not available.",
        )
    if sum(len(t) for _, t in parsed) > 500000:
        raise SireError(
            "document_too_large", "Extracted source text exceeds the limit.", 413
        )
    sha = hashlib.sha256(content).hexdigest()
    directory = ledger.store.path.parent / "imports"
    directory.mkdir(exist_ok=True)
    destination = directory / (sha + suffix)
    if (
        destination.exists()
        and hashlib.sha256(destination.read_bytes()).hexdigest() != sha
    ):
        raise SireError("source_integrity", "Stored source bytes differ.", 503)
    if not destination.exists():
        imports = [p for p in directory.iterdir() if p.is_file()]
        if (
            len(imports) >= SETTINGS["max_import_files"]
            or sum(p.stat().st_size for p in imports) + len(content)
            > SETTINGS["max_import_bytes"]
        ):
            raise SireError("import_quota", "Private import quota reached.", 413)
        destination.write_bytes(content)
    rows = []
    for locator, text in parsed:
        # Exact excerpt boundaries are retained even when a paragraph/row is long.
        for offset in range(0, len(text), 1200):
            row = ledger.add(
                "real_uploaded",
                name,
                {"excerpt": text[offset : offset + 1200]},
                {
                    "filename": name,
                    "locator": locator,
                    "character_start": offset,
                    "character_end": min(offset + 1200, len(text)),
                },
                method="bounded_parse_v1",
                quality="user_supplied_unverified",
                content_sha256=sha,
                mime=mime,
                size_bytes=len(content),
                storage_locator="private_import:" + sha + suffix,
            )
            rows.append(row.id)
    return {
        "source_type": "real_uploaded",
        "filename": name,
        "original_sha256": sha,
        "bytes": len(content),
        "evidence_ids": rows,
        "source_authenticity": "unverified",
        "warnings": [
            "Local audit snapshots retain source excerpts/originals; they are not verified physical facts.",
            "No C-MAPSS compatibility or physical asset linkage is inferred.",
        ],
    }
