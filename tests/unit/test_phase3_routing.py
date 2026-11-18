"""Mixed-modal history and saved-case routing regressions, not phrase-only fallback answers."""

from pathlib import Path
import pytest
from app.orchestration.case_context import recall_requested
from app.chat.conversation import source_followup
from app.knowledge.ingestion import ingest
from app.knowledge.search import search
from app.storage.database import Store


@pytest.mark.parametrize(
    "question",
    [
        "Show saved hypotheses.",
        "Explain previous findings.",
        "Compare those candidates.",
        "What have we found so far?",
        "Why was that hypothesis rejected?",
    ],
)
def test_saved_followups_recognize_singular_plural_and_natural_word_order(question):
    assert recall_requested(question)


@pytest.mark.parametrize(
    "question",
    [
        "Show saved hypotheses then rerun with new evidence.",
        "Investigate again and compare previous findings.",
        "Explain rolling bearings in general.",
    ],
)
def test_fresh_analysis_and_general_questions_are_not_recalled(question):
    assert not recall_requested(question)


def test_explicit_without_evidence_does_not_pull_old_documents_unnecessarily():
    assert not source_followup(
        "Give a detailed explanation of friction without machine-specific evidence."
    )
    assert source_followup(
        "There are no measurements, but compare the attached manual."
    )


def test_audio_transcript_chunks_are_not_retrieved_as_document_evidence(tmp_path: Path):
    store = Store(tmp_path / "test.sqlite3")
    cid = store.create_conversation()["id"]
    doc = ingest(
        store,
        cid,
        "TEST-ONLY-manual.txt",
        b"TEST-ONLY maintenance vibration inspection guidance.",
    )
    audio = ingest(
        store,
        cid,
        "TEST-ONLY-transcript.txt",
        b"TEST-ONLY user speech mentions vibration. This is input provenance.",
    )
    with store.connection() as db:
        db.execute(
            "UPDATE attachments SET kind='audio',name='TEST-ONLY.wav' WHERE id=?",
            (audio["id"],),
        )
    rows = search(store, cid, "vibration", mode="lexical")
    assert rows and {row["attachment_id"] for row in rows} == {doc["id"]}
