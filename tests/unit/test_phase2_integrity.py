"""Real source corruption, excerpt fidelity and conservative narrative review controls."""

from pathlib import Path
import pytest
from app.core.errors import SireError
from app.knowledge.ingestion import ingest
from app.knowledge.search import search
from app.storage.database import Store
from app.investigation.narrative import issues
from app.voice.chunks import split_text
from app.core.process_metrics import usage


def test_source_byte_change_and_forged_excerpt_are_withheld(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.sqlite3")
    cid = store.create_conversation()["id"]
    receipt = ingest(
        store, cid, "TEST-ONLY.txt", b"TEST-ONLY: record the actual pressure."
    )
    item = store.attachment(receipt["id"], cid)
    assert search(store, cid, "pressure", mode="lexical")
    with store.connection() as db:
        db.execute(
            "UPDATE chunks SET text=? WHERE attachment_id=?",
            ("TEST-ONLY forged excerpt", item["id"]),
        )
    with pytest.raises(SireError) as error:
        search(store, cid, "pressure", mode="lexical")
    assert error.value.code == "source_chunk_integrity"
    Path(item["path"]).write_bytes(b"TEST-ONLY altered source bytes")
    with pytest.raises(SireError) as error:
        search(store, cid, "pressure", mode="lexical")
    assert error.value.code == "source_integrity"


def test_speech_segmentation_preserves_words_and_enforces_limits() -> None:
    text = "TEST-ONLY sentence one. Another test-only sentence with words."
    chunks = split_text(text, 25, 6)
    assert " ".join(chunks) == text and all(len(c) <= 25 for c in chunks)
    with pytest.raises(SireError):
        split_text("x" * 26, 25, 6)
    with pytest.raises(SireError):
        split_text(text, 25, 1)


def test_narrative_review_and_actual_process_counters() -> None:
    assert issues("Lubrication starvation due to")
    assert issues("Wear (tentative")
    assert issues("Wear produces a change in the recorded baseline, ")
    assert issues("")
    assert not issues("Lubrication starvation can produce surface wear.")
    metrics = usage()
    assert metrics["cpu_seconds"] >= 0 and metrics["peak_rss_bytes"] > 0
