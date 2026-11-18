"""Focused known-failure controls; these do not estimate industrial diagnostic accuracy."""

import asyncio
from pathlib import Path
from app.investigation import engine
from app.investigation.schemas import Case, EvidenceItem, Hypothesis, Proposal
from app.evidence.measurements import profile
from app.knowledge.ingestion import ingest
from app.voice.text import spoken_text, _lexicon_words


def candidate(identifier: str, mechanism: str) -> Hypothesis:
    """Construct explicitly test-only candidate definitions."""
    return Hypothesis(
        id=identifier,
        mechanism=mechanism,
        assumptions=[],
        expected_signs=[],
        supporting_evidence_ids=[],
        contradicting_evidence_ids=[],
        missing_tests=["Test-only inspection"],
    )


def test_equal_support_ties_do_not_select_by_alphabetical_identifier():
    case = Case(question="Test-only", conversation_id="test-only", evidence=[])
    rows = engine.rank_hypotheses(
        case,
        [
            candidate("z", "Test-only bearing wear."),
            candidate("a", "Test-only lubrication loss."),
        ],
    )
    assert [r["id"] for r in rows] == ["z", "a"]


def test_incomplete_mechanism_marked_and_complete_equal_support_prioritized():
    case = Case(question="Test-only", conversation_id="test-only", evidence=[])
    rows = engine.rank_hypotheses(
        case,
        [
            candidate("a", "Test-only wear due to"),
            candidate("z", "Test-only bearing wear."),
        ],
    )
    assert (
        rows[0]["id"] == "z" and rows[0]["quality_status"] == "complete_text_unverified"
    )
    assert (
        rows[1]["quality_status"] == "incomplete_text" and rows[1]["narrative_issues"]
    )
    assert all(row["diagnostic_checks_provided"] for row in rows)


def test_mechanism_cannot_claim_existing_channel_is_missing(
    store, monkeypatch, sync_proposal_transport
):
    cid = store.create_conversation()["id"]
    upload = ingest(
        store,
        cid,
        "TEST-ONLY.csv",
        b"asset_id,timestamp_utc,vibration_mm_s\nUNIT-777,2026-01-01T00:00:00Z,1\nUNIT-777,2026-01-01T01:00:00Z,2\n",
    )
    group = profile(store, cid, upload["id"])["groups"][0]
    case = Case(
        question="TEST-ONLY investigation",
        conversation_id=cid,
        asset_id="UNIT-777",
        evidence=[
            EvidenceItem(
                id=group["evidence_id"],
                source_id=upload["id"],
                kind="measurement",
                modality="uploaded_measurements",
                asset_identity="UNIT-777",
                observation="TEST-ONLY source readings",
                reliability="medium",
            )
        ],
    )
    proposal = Proposal(
        hypotheses=[candidate("test-only", "Vibration data are missing for UNIT-777.")],
        follow_up_queries=[],
        unresolved=[],
    )
    monkeypatch.setattr(engine.ollama, "generate", lambda *args: proposal)
    result = asyncio.run(engine.investigate(store, case, asyncio.Event()))
    assert not result.hypotheses
    assert any(row["status"] == "contradicted" for row in result.claim_verification)
    assert any("Available source readings" in text for text in result.unresolved)


def test_lexicon_reuse_is_bound_to_actual_bytes_and_temperature_units(tmp_path: Path):
    lexicon = tmp_path / "test-only.txt"
    lexicon.write_text("one W\ndegrees D\nCelsius C\nFahrenheit F\n", encoding="utf-8")
    first = spoken_text("1°C", lexicon)
    assert first[0] == "one degrees Celsius"
    second = spoken_text("1°F", lexicon)
    assert second[0] == "one degrees Fahrenheit"
    before = _lexicon_words.cache_info()
    spoken_text("1°C", lexicon)
    assert _lexicon_words.cache_info().hits > before.hits
    changed = lexicon.read_bytes() + b"new N\n"
    assert "new" in _lexicon_words(changed)
