"""Actual engine preservation and provider exhaustion diagnostics with explicit unit fixtures."""

import asyncio
import httpx
import pytest
from app.core.errors import SireError
from app.investigation import engine
from app.investigation.schemas import Case, EvidenceItem, Hypothesis, Proposal
from app.knowledge.ingestion import ingest
from app.providers import ollama

pytestmark = pytest.mark.usefixtures("sync_proposal_transport")


def test_failed_followup_preserves_actual_completed_round(store, monkeypatch):
    cid = store.create_conversation()["id"]
    ingest(
        store, cid, "test-only.txt", b"Independent inspection of pressure is required."
    )
    source = EvidenceItem(
        id="test-only-claim",
        source_id="test-only",
        modality="text",
        kind="user_claim",
        observation="Test-only pressure concern",
    )
    proposal = Proposal(
        hypotheses=[
            Hypothesis(
                id="test-only-hypothesis",
                mechanism="Test-only pressure loss",
                assumptions=[],
                expected_signs=[],
                supporting_evidence_ids=[source.id],
                contradicting_evidence_ids=[],
                missing_tests=["Independent pressure inspection"],
            )
        ],
        follow_up_queries=["Independent inspection pressure"],
        unresolved=[],
    )
    calls = []

    def generate(*args):
        calls.append(args)
        if len(calls) == 1:
            return proposal
        raise SireError("llm_response_limit", "Test-only exhausted follow-up", 503)

    monkeypatch.setattr(engine.ollama, "generate", generate)
    result = asyncio.run(
        engine.investigate(
            store,
            Case(question="Test-only case", conversation_id=cid, evidence=[source]),
            asyncio.Event(),
        )
    )
    assert len(calls) == 2 and result.rounds == 1 and result.hypotheses
    assert result.stop_reason == "followup_failed_prior_round_preserved"
    assert result.followup_error["code"] == "llm_response_limit"
    assert [tool.status for tool in result.tools] == ["complete", "complete", "error"]


def test_structured_token_exhaustion_is_reported_before_json_parse(monkeypatch):
    monkeypatch.setattr(ollama, "readiness", lambda: {"models": ["test-only"]})
    monkeypatch.setattr(
        ollama.httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(
            200,
            request=httpx.Request("POST", "http://127.0.0.1"),
            json={"done_reason": "length", "message": {"content": '{"hypotheses": ['}},
        ),
    )
    with pytest.raises(SireError) as failure:
        ollama.generate([], Proposal, "test-only")
    assert failure.value.code == "llm_response_limit"


def test_uploaded_sensor_asset_is_not_associated_with_a_photo_by_proximity():
    image = EvidenceItem(
        id="test-only-image",
        source_id="image",
        modality="image",
        kind="model_inference",
        observation="Unlinked synthetic drawing",
    )
    measured = EvidenceItem(
        id="test-only-sensor",
        source_id="csv",
        modality="uploaded_measurements",
        kind="measurement",
        observation="A different user-declared asset",
        asset_identity="TEST-ONLY-PUMP-001",
        reliability="medium",
    )
    hypothesis = Hypothesis(
        id="test-only",
        mechanism="Test-only wear",
        assumptions=[],
        expected_signs=[],
        supporting_evidence_ids=[measured.id],
        contradicting_evidence_ids=[],
        missing_tests=[],
    )
    result = engine.rank_hypotheses(
        Case(
            question="Test-only",
            conversation_id="test-only",
            evidence=[image, measured],
        ),
        [hypothesis],
    )[0]
    assert result["excluded_as_unlinked"] == [measured.id]
    assert result["ranking_score"] == 0 and result["evidence_support"] == "low"


def test_free_text_source_aliases_are_resolved_and_unknown_alias_is_rejected():
    from app.investigation.proposal_schema import expand

    proposal = Proposal(
        hypotheses=[],
        follow_up_queries=[],
        unresolved=["Unverified model interpretation [E2]"],
    )
    identifier = "EV:" + "a" * 64
    assert expand(proposal, {"E2": identifier}).unresolved == [
        f"Unverified model interpretation [{identifier}]"
    ]
    with pytest.raises(SireError):
        expand(proposal, {"E1": identifier})
