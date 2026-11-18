"""Real optional local semantic inference and deterministic source/index controls."""

from pathlib import Path
import io
import zipfile
import pytest
from app.core.errors import SireError
from app.knowledge import embeddings
from app.knowledge.ingestion import ingest
from app.knowledge.search import search
from app.knowledge.semantic import clear
from app.storage.database import Store


def test_named_document_retains_two_matching_accounts_over_generic_guidance(
    tmp_path: Path,
) -> None:
    """Filename relevance helps select both accounts; exact codes still require body hits."""
    store = Store(tmp_path / "test.sqlite3")
    cid = store.create_conversation()["id"]
    paragraphs = [
        "Test-only conflicting shift handover",
        "Test-only operator A: filter was replaced. Source: SHIFT-A.",
        "Test-only operator B: filter replacement was deferred. Source: SHIFT-B.",
    ]
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            + "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
            + "</w:body></w:document>",
        )
    report = ingest(store, cid, "conflicting_shift_handover.docx", archive.getvalue())
    ingest(
        store,
        cid,
        "test-only-manual.txt",
        b"Test-only general guidance: compare supplied data and identify evidence for maintenance work and sensor measurements.",
    )
    result = search(
        store,
        cid,
        "Compare conflicting shift handover accounts about filter replacement with supplied sensor data and evidence for maintenance work.",
        mode="lexical",
    )
    accounts = [
        row["excerpt"] for row in result if row["attachment_id"] == report["id"]
    ]
    assert any("SHIFT-A" in text for text in accounts)
    assert any("SHIFT-B" in text for text in accounts)
    assert search(store, cid, "PUMP-001", mode="lexical") == []


def test_unavailable_requested_semantics_does_not_fabricate_vectors(
    monkeypatch, tmp_path: Path
) -> None:
    store = Store(tmp_path / "test.sqlite3")
    cid = store.create_conversation()["id"]
    ingest(store, cid, "test-only.txt", b"TEST-ONLY source for local retrieval.")
    monkeypatch.setattr(embeddings, "readiness", lambda: {"configured": False})
    with pytest.raises(SireError) as e:
        search(store, cid, "conceptual question", mode="semantic")
    assert e.value.code == "embedding_unavailable"


@pytest.mark.skipif(
    not embeddings.readiness()["configured"],
    reason="Optional local semantic runtime/model not installed",
)
def test_actual_semantic_search_is_case_scoped_persistent_and_rebuildable(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "test.sqlite3")
    cid = store.create_conversation()["id"]
    other = store.create_conversation()["id"]
    source = ingest(
        store,
        cid,
        "test-only-drive.txt",
        b"TEST-ONLY: An inverter regulates the rotational velocity of an electric motor.",
    )
    ingest(
        store,
        other,
        "test-only-other.txt",
        b"TEST-ONLY: A variable frequency drive controls speed in a different case.",
    )
    assert search(store, cid, "variable frequency drive", mode="lexical") == []
    results = search(store, cid, "variable frequency drive", mode="semantic")
    assert results and {r["attachment_id"] for r in results} == {source["id"]}
    assert results[0]["retrieval"]["new_vectors"] == 1
    repeated = search(store, cid, "variable frequency drive", mode="semantic")
    assert repeated[0]["retrieval"]["new_vectors"] == 0
    assert (
        search(
            store,
            cid,
            "variable frequency drive",
            mode="semantic",
            as_of="2000-01-01T00:00:00Z",
        )
        == []
    )
    assert clear(store, cid) == 1
    assert (
        search(store, cid, "variable frequency drive", mode="semantic")[0]["retrieval"][
            "new_vectors"
        ]
        == 1
    )
