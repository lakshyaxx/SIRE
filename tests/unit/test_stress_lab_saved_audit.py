"""Metadata source mapping does not treat narrative strings as additional evidence."""

from scripts.stress_lab.saved_audit import message_references
import json
import scripts.stress_lab.saved_audit as module
from app.evidence.ledger import Ledger


def test_saved_reference_collection_preserves_order_and_unifies_actual_metadata():
    metadata = {
        "workspace": {"evidence_ids": ["EV:test-only", "EV:test-only"]},
        "evidence": [{"id": "legacy-test-only"}, {"id": "EV:test-only"}],
        "narrative": "[made-up-source] is not a supplied reference",
    }
    assert message_references(metadata) == ["EV:test-only", "legacy-test-only"]
    assert message_references({}) == []


def test_read_only_saved_audit_exposes_late_evidence_without_creating_a_new_reply(
    tmp_path, store, monkeypatch
):
    monkeypatch.setattr(module, "ROOT", tmp_path)
    root = tmp_path / ".runtime/stress_lab"
    root.mkdir(parents=True)
    corpus = tmp_path / "test-only-public"
    (corpus / "facility").mkdir(parents=True)
    (corpus / "facility/sire_synthetic_facility.sqlite3").write_bytes(b"")
    cid = store.create_conversation("Test-only saved late evidence")["id"]
    record = Ledger(store).add(
        "manually_entered",
        "Test-only late note",
        {"note": "Test-only unverified note"},
        {"test_only": True},
        available_at="2026-01-02T00:00:00+00:00",
    )
    store.add_message(
        cid,
        "assistant",
        "Test-only saved answer",
        metadata={
            "workspace": {
                "evidence_ids": [record.id],
                "context": {"as_of": "2026-01-01T00:00:00+00:00"},
            }
        },
    )
    answers = root / "answers.jsonl"
    answers.write_text(
        json.dumps({"test_id": "TEST-ONLY", "executed": True, "conversation_id": cid})
        + "\n",
        encoding="utf-8",
    )
    before = store.messages(cid)
    result = module.audit_saved(
        answers, store.path.parent, store.path.parent, corpus, root / "test-only-output"
    )
    assert result["future_violations"] == 1
    assert result["supported_snapshot_checks"] == 0
    assert store.messages(cid) == before
