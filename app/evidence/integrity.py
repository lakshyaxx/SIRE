"""Source-byte fidelity checks before reusing or interpreting an attachment."""

import hashlib
from pathlib import Path
from app.core.config import SETTINGS
from app.core.errors import SireError
from app.storage.database import Store


def read_verified(item: dict) -> bytes:
    """Read the stored bytes only when their original recorded identity still matches."""
    path = Path(item["path"])
    try:
        if path.stat().st_size > SETTINGS["max_upload_bytes"]:
            raise SireError(
                "source_integrity",
                "Stored source exceeds its recorded upload limit.",
                409,
            )
        content = path.read_bytes()
    except OSError as exc:
        raise SireError(
            "source_unavailable", "The original local source is unavailable.", 404
        ) from exc
    if hashlib.sha256(content).hexdigest() != item["sha256"]:
        raise SireError(
            "source_integrity",
            "Stored source bytes changed; interpretation withheld.",
            409,
        )
    return content


def validate_chunks(store: Store, conversation_id: str, chunks: list[dict]) -> None:
    """Reproduce deterministic source chunks before returning excerpts or indexing them."""
    from app.knowledge.ingestion import extract_document

    expected = {}
    for identifier in {c["attachment_id"] for c in chunks}:
        item = store.attachment(identifier, conversation_id)
        content = read_verified(item)
        sections = extract_document(content, Path(item["name"]).suffix.lower())
        for locator, text in sections:
            for offset in range(0, len(text), 1200):
                excerpt = text[offset : offset + 1200]
                if excerpt.strip():
                    key = hashlib.sha256(
                        f"{identifier}:{locator}:{offset}:{excerpt}".encode()
                    ).hexdigest()[:24]
                    expected[key] = (
                        excerpt,
                        f"{locator}, chars {offset+1}-{offset+len(excerpt)}",
                    )
    for chunk in chunks:
        if expected.get(chunk["id"]) != (chunk["text"], chunk["locator"]):
            raise SireError(
                "source_chunk_integrity",
                "Indexed excerpt differs from the actual source; retrieval withheld.",
                409,
            )
