"""Candidate retention, unfamiliar asset scope, exact inventory and historical follow-up fences."""

import asyncio
import pytest
import json
from app.evidence.inventory import inventory, check_absence
from app.evidence.ledger import Ledger
from app.evidence.measurements import profile
from app.investigation.engine import investigate, rank_hypotheses
from app.investigation.identity import merge
from app.investigation.registry import registry_rows
from app.investigation.schemas import (
    Case,
    EvidenceItem,
    ExpectedSign,
    Hypothesis,
    Proposal,
)
from app.knowledge.ingestion import ingest

pytestmark = pytest.mark.usefixtures("sync_proposal_transport")


def candidate(name, support=None):
    """Build explicit unit-only proposals; these are never production fallback answers."""
    return Hypothesis(
        id=name,
        mechanism=name,
        assumptions=[],
        expected_signs=[],
        supporting_evidence_ids=support or [],
        contradicting_evidence_ids=[],
        missing_tests=[],
    )


def test_candidates_after_eight_are_retained_and_selected_by_evidence():
    original = [candidate("Test-only mechanism " + chr(65 + i)) for i in range(12)]
    original[-1].supporting_evidence_ids = ["test-only-measured"]
    merged, _ = merge(original)
    assert len(merged) == 12
    case = Case(
        question="Unfamiliar compressor",
        conversation_id="test-only",
        asset_id="UNIT-777",
        evidence=[
            EvidenceItem(
                id="test-only-measured",
                source_id="test-only",
                modality="instrument",
                kind="measurement",
                observation="Explicit test-only independent observation",
                asset_identity="UNIT-777",
                reliability="high",
            )
        ],
    )
    ranked = rank_hypotheses(case, merged)
    rows = registry_rows("test-only-case-a", merged, ranked, 1)
    assert (
        len(rows) == 12 and sum(r["selection_state"] == "deferred" for r in rows) == 4
    )
    assert rows[0]["definition"]["mechanism"] == original[-1].mechanism
    assert (
        rows[0]["case_hypothesis_id"]
        != registry_rows("test-only-case-b", merged, ranked, 1)[0]["case_hypothesis_id"]
    )


def test_unrelated_measurement_does_not_falsify_and_renaming_preserves_result():
    wrong = EvidenceItem(
        id="test-only-wrong",
        source_id="test-only-source",
        modality="instrument",
        kind="measurement",
        observation="A different equipment's boolean check",
        asset_identity="OTHER-992",
        predicate="test_only_pressure_low",
        value=False,
        reliability="high",
    )
    h = candidate("Test-only pressure mechanism", [wrong.id])
    h.expected_signs = [
        ExpectedSign(predicate="test_only_pressure_low", expected_value=True)
    ]
    first = rank_hypotheses(
        Case(
            question="Test-only",
            conversation_id="test",
            asset_id="UNIT-777",
            evidence=[wrong],
        ),
        [h],
    )[0]
    assert (
        first["status"] == "tentative"
        and not first["falsified_by"]
        and first["ranking_score"] == 0
    )
    assert first["excluded_as_unlinked"] == [wrong.id]
    correct = wrong.model_copy(update={"asset_identity": "UNIT-777"})
    old = rank_hypotheses(
        Case(
            question="Test-only",
            conversation_id="test",
            asset_id="UNIT-777",
            evidence=[correct],
        ),
        [h],
    )[0]
    renamed = correct.model_copy(update={"asset_identity": "UNFAMILIAR-435"})
    new = rank_hypotheses(
        Case(
            question="Test-only",
            conversation_id="test",
            asset_id="UNFAMILIAR-435",
            evidence=[renamed],
        ),
        [h],
    )[0]
    assert (
        old["status"] == new["status"] == "rejected"
        and old["ranking_score"] == new["ranking_score"]
    )


def test_availability_uses_actual_good_rows_and_does_not_confuse_assets(store):
    cid = store.create_conversation()["id"]
    upload = ingest(
        store,
        cid,
        "test-only.csv",
        b"asset_id,timestamp_utc,flow_m3_h,ambient_temp_c\nUNIT-777,2026-01-01T00:00:00Z,12,20\nUNIT-777,2026-01-01T01:00:00Z,13,21\n",
    )
    groups = profile(store, cid, upload["id"])["groups"]
    evidence = [
        EvidenceItem(
            id=g["evidence_id"],
            source_id=upload["id"],
            modality="uploaded_measurements",
            kind="measurement",
            observation=json.dumps(g),
            asset_identity=g["asset_id"],
        )
        for g in groups
    ]
    available = inventory(
        Case(question="Test-only", conversation_id=cid, evidence=evidence),
        Ledger(store),
    )
    corrected, checks = check_absence(
        [
            "No flow rate data is available for UNIT-777.",
            "No ambient temperature delta is provided.",
            "No flow rate data is available for OTHER-992.",
            "Flow measurements are insufficient for this mechanism.",
        ],
        available,
    )
    assert [c["status"] for c in checks] == [
        "contradicted",
        "contradicted",
        "unverified",
        "unverified",
    ]
    assert (
        "2 good rows" in corrected[0]
        and "diagnostic sufficiency remains unverified" in corrected[0]
    )
    assert (
        inventory(
            Case(
                question="Test-only",
                conversation_id=cid,
                evidence=evidence,
                as_of="2020-01-01T00:00:00Z",
            ),
            Ledger(store),
        )
        == []
    )


def test_future_initial_and_followup_document_text_never_reaches_model(
    store, monkeypatch
):
    from app.investigation import engine

    cid = store.create_conversation()["id"]
    ledger = Ledger(store)
    user = ledger.add(
        "manually_entered",
        "Test-only old claim",
        {"claim": "Old test claim"},
        {"test_only": True},
        available_at="2026-01-01T00:00:00+00:00",
    )
    uploaded = ingest(
        store,
        cid,
        "test-only-future.txt",
        b"Future secret test-only measurement number 9988; discriminating inspection evidence.",
    )
    chunk = store.rows("SELECT * FROM chunks WHERE attachment_id=?", (uploaded["id"],))[
        0
    ]
    evidence = [
        EvidenceItem(
            id=user.id,
            source_id=user.source_id,
            modality="text",
            kind="user_claim",
            observation="Old test-only user claim",
        ),
        EvidenceItem(
            id=chunk["id"],
            source_id=uploaded["id"],
            modality="document",
            kind="document_guidance",
            observation=chunk["text"],
        ),
    ]
    calls = []

    def propose(messages, *args):
        calls.append(messages)
        return Proposal(
            hypotheses=[candidate("Test-only mechanism", [user.id])],
            follow_up_queries=["discriminating inspection evidence"],
            unresolved=[],
        )

    monkeypatch.setattr(engine.ollama, "generate", propose)
    result = asyncio.run(
        investigate(
            store,
            Case(
                question="Test-only historical investigation",
                conversation_id=cid,
                as_of="2026-01-02T00:00:00Z",
                evidence=evidence,
            ),
            asyncio.Event(),
        )
    )
    assert len(calls) == 1 and "9988" not in json.dumps(calls)
    assert len(result.case.evidence) == 1 and result.excluded_evidence
    assert (
        result.tools[-1].tool == "search_documents"
        and result.tools[-1].source_ids == []
    )


def test_more_passages_from_same_manual_do_not_force_another_expensive_round(
    store, monkeypatch
):
    from app.investigation import engine

    cid = store.create_conversation()["id"]
    upload = ingest(
        store,
        cid,
        "test-only-manual.txt",
        (
            "Inspection pressure note. " * 60
            + "Independent discriminator guideline. " * 60
        ).encode(),
    )
    chunk = store.rows(
        "SELECT * FROM chunks WHERE attachment_id=? ORDER BY rowid", (upload["id"],)
    )[0]
    evidence = [
        EvidenceItem(
            id=chunk["id"],
            source_id=upload["id"],
            modality="document",
            kind="document_guidance",
            observation=chunk["text"],
        )
    ]
    calls = []

    def propose(*args):
        calls.append(args)
        return Proposal(
            hypotheses=[candidate("Test-only mechanism", [chunk["id"]])],
            follow_up_queries=["independent discriminator guideline"],
            unresolved=[],
        )

    monkeypatch.setattr(engine.ollama, "generate", propose)
    result = asyncio.run(
        investigate(
            store,
            Case(question="Test-only", conversation_id=cid, evidence=evidence),
            asyncio.Event(),
        )
    )
    assert (
        len(calls) == 1
        and result.stop_reason == "guidance_saved_no_independent_evidence_change"
    )
    assert len(result.case.evidence) > 1 and result.hypothesis_registry


def test_duplicate_measurements_across_csv_json_have_one_semantic_origin(store):
    cid = store.create_conversation()["id"]
    a = ingest(
        store,
        cid,
        "test-only.csv",
        b"asset_id,timestamp,channel,value,unit\nUNIT-777,2026-01-01T00:00:00Z,flow,12,m3/h\n",
    )
    b = ingest(
        store,
        cid,
        "test-only.json",
        json.dumps(
            [
                {
                    "asset_id": "UNIT-777",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "channel": "flow",
                    "value": 12,
                    "unit": "m3/h",
                }
            ]
        ).encode(),
    )
    assert (
        a["id"] != b["id"]
        and a["metadata"]["measurement_content_sha256"]
        == b["metadata"]["measurement_content_sha256"]
    )


def test_expected_sign_aliases_resolve_and_unknown_citation_is_rejected():
    from app.investigation.proposal_schema import expand
    from app.core.errors import SireError

    source = "EV:" + "f" * 64
    proposed = Proposal(
        hypotheses=[
            Hypothesis(
                id="test-only",
                mechanism="Test-only possible wear",
                assumptions=[],
                expected_signs=[
                    {"predicate": "vibration rises [E1]", "expected_value": True}
                ],
                supporting_evidence_ids=["E1"],
                contradicting_evidence_ids=[],
                missing_tests=[],
            )
        ],
        follow_up_queries=["Inspection logs [E1]"],
        unresolved=[],
    )
    expanded = expand(proposed, {"E1": source})
    assert (
        expanded.hypotheses[0].expected_signs[0].predicate
        == f"vibration rises [{source}]"
    )
    assert expanded.follow_up_queries == [f"Inspection logs [{source}]"]
    with pytest.raises(SireError):
        expand(proposed, {"E2": source})


def test_revision_inherits_existing_asset_and_cutoff_without_mixing_scopes(
    store, monkeypatch
):
    from app.investigation import engine

    cid = store.create_conversation()["id"]
    monkeypatch.setattr(
        engine.ollama,
        "generate",
        lambda *args: Proposal(
            hypotheses=[],
            follow_up_queries=[],
            unresolved=["No independent source measurements available."],
        ),
    )
    first = asyncio.run(
        investigate(
            store,
            Case(
                question="Test-only",
                conversation_id=cid,
                evidence=[],
                asset_id="UNIT-777",
                as_of="2026-01-01T00:00:00Z",
            ),
            asyncio.Event(),
        )
    )
    parent = store.save_result("cases", first.model_dump(), cid)
    revised = asyncio.run(
        investigate(
            store,
            Case(
                question="Revise test-only",
                conversation_id=cid,
                evidence=[],
                parent_case_id=parent,
            ),
            asyncio.Event(),
        )
    )
    assert (
        revised.case.asset_id == "UNIT-777"
        and revised.case.as_of == first.case.as_of
        and revised.case_key == first.case_key
    )
