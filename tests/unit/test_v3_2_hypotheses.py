"""Stable candidate identity, ambiguity-aware merging and genuine measured revision rules."""

import asyncio
import pytest
from app.investigation.identity import merge
from app.investigation.schemas import (
    Case,
    EvidenceItem,
    Hypothesis,
    ExpectedSign,
    Proposal,
)
from app.investigation.engine import investigate
from app.orchestration.planner import investigation_requested

pytestmark = pytest.mark.usefixtures("sync_proposal_transport")


def candidate(
    identifier: str, name: str, support: list[str], conflict: list[str] | None = None
) -> Hypothesis:
    """Create a clearly test-only proposal, never application fallback content."""
    return Hypothesis(
        id=identifier,
        mechanism=name,
        assumptions=[],
        expected_signs=[
            ExpectedSign(predicate="test_only_pressure_low", expected_value=True)
        ],
        supporting_evidence_ids=support,
        contradicting_evidence_ids=conflict or [],
        missing_tests=["Independent test-only pressure inspection"],
    )


def test_known_aliases_merge_stably_and_ambiguous_source_does_not_falsify():
    one = candidate("test-only-a", "Insufficient lubrication", ["source-1"])
    two = candidate("test-only-b", "Inadequate lubrication", [], ["source-1"])
    merged, records = merge([one, two])
    assert len(merged) == 1
    assert merged[0].id == merge([two])[0][0].id
    assert (
        not merged[0].supporting_evidence_ids
        and not merged[0].contradicting_evidence_ids
    )
    assert records[0]["ambiguous_source_ids"] == ["source-1"]
    assert "ambiguous" in merged[0].missing_tests[-1]


def test_general_method_question_avoids_incident_engine():
    assert not investigation_requested("What is a hypothesis investigation?")
    assert investigation_requested("Investigate this bearing using the attached photo")
    assert investigation_requested("Revise this investigation with the new inspection")
    assert investigation_requested("Hello", True)
    assert not investigation_requested(
        "Describe visible features in this video; it contains no evidence of real mechanical motion or failure."
    )
    assert not investigation_requested(
        "Describe this bearing without fault investigation"
    )


def test_correlated_frame_observations_do_not_count_as_independent_support():
    from app.investigation.engine import rank_hypotheses

    evidence = [
        EvidenceItem(
            id=f"test-only-frame-{i}",
            source_id=f"test-only-image-{i}",
            origin_id="test-only-one-recording",
            modality="video_frame",
            kind="model_inference",
            observation="Test-only visible construction",
            reliability="medium",
        )
        for i in range(4)
    ]
    case = Case(question="Test-only", conversation_id="test-only", evidence=evidence)
    ranked = rank_hypotheses(
        case,
        [
            candidate(
                "test-only", "Insufficient lubrication", [row.id for row in evidence]
            )
        ],
    )
    assert ranked[0]["ranking_score"] == 0.25 and ranked[0]["evidence_support"] == "low"


def test_lexical_identity_does_not_merge_reversed_causal_statements():
    one = candidate("test-only-a", "contamination causes bearing wear", [])
    two = candidate("test-only-b", "bearing wear causes contamination", [])
    assert len(merge([one, two])[0]) == 2


def test_actual_engine_abstains_without_forcing_candidate_count(store, monkeypatch):
    from app.investigation import engine

    monkeypatch.setattr(
        engine.ollama,
        "generate",
        lambda *args: Proposal(
            hypotheses=[],
            follow_up_queries=[],
            unresolved=["No independent measurements are available."],
        ),
    )
    cid = store.create_conversation()["id"]
    result = asyncio.run(
        investigate(
            store,
            Case(
                question="Test-only insufficient evidence",
                conversation_id=cid,
                evidence=[],
            ),
            asyncio.Event(),
        )
    )
    assert not result.hypotheses and result.stop_reason == "insufficient_evidence"
    assert result.hypothesis_revisions[0]["candidates"] == []


def test_language_script_drift_is_marked_incomplete():
    from app.investigation import engine

    case = Case(question="Test-only", conversation_id="test-only", evidence=[])
    row = engine.rank_hypotheses(
        case,
        [candidate("a", "Progressive degradation of潤", [])],
    )[0]
    assert row["quality_status"] == "incomplete_text"
    assert any("script drift" in issue for issue in row["narrative_issues"])


def test_incomplete_proposal_is_withheld_with_original_trace(store, monkeypatch):
    from app.investigation import engine

    cid = store.create_conversation()["id"]
    proposal = Proposal(
        hypotheses=[candidate("unfinished", "Progressive degradation due to", [])],
        follow_up_queries=[],
        unresolved=[],
    )
    monkeypatch.setattr(engine.ollama, "generate", lambda *args: proposal)
    result = asyncio.run(
        investigate(
            store,
            Case(question="Test-only", conversation_id=cid, evidence=[]),
            asyncio.Event(),
        )
    )
    assert result.hypotheses == []
    assert result.stop_reason == "insufficient_evidence"
    assert "was withheld" in result.unresolved[0]
    rejection = result.hypothesis_revisions[0]["quality_rejections"][0]
    assert rejection["candidate"]["mechanism"] == "Progressive degradation due to"
    assert rejection["reasons"]


def test_revision_rechecks_prior_candidate_against_new_measured_contradiction(
    store, monkeypatch
):
    from app.investigation import engine

    cid = store.create_conversation()["id"]
    old_claim = EvidenceItem(
        id="test-only-claim",
        modality="text",
        kind="user_claim",
        source_id="test-only",
        observation="Test-only low pressure claim",
        reliability="low",
    )
    proposal = Proposal(
        hypotheses=[
            candidate("test-only-proposal", "Insufficient lubrication", [old_claim.id])
        ],
        follow_up_queries=[],
        unresolved=[],
    )
    monkeypatch.setattr(engine.ollama, "generate", lambda *args: proposal)
    prior = asyncio.run(
        investigate(
            store,
            Case(question="Test-only", conversation_id=cid, evidence=[old_claim]),
            asyncio.Event(),
        )
    )
    parent = store.save_result("cases", prior.model_dump(), cid)
    observed = EvidenceItem(
        id="test-only-measured",
        modality="inspection",
        kind="measurement",
        source_id="test-only-measurement",
        observation="Test-only independently measured predicate",
        reliability="high",
        predicate="test_only_pressure_low",
        value=False,
    )
    revised = asyncio.run(
        investigate(
            store,
            Case(
                question="Revise test-only case",
                conversation_id=cid,
                evidence=[observed],
                parent_case_id=parent,
            ),
            asyncio.Event(),
        )
    )
    assert revised.hypotheses[0]["id"] == prior.hypotheses[0]["id"]
    assert (
        revised.hypotheses[0]["status"] == "rejected"
        and observed.id in revised.hypotheses[0]["falsified_by"]
    )
    assert store.result("cases", parent)["hypotheses"][0]["status"] == "tentative"


def test_decoding_schema_only_accepts_actual_case_source_ids():
    from pydantic import ValidationError
    from app.investigation.proposal_schema import for_case

    case = Case(
        question="Test-only",
        conversation_id="test-only",
        evidence=[
            EvidenceItem(
                id="known-test-source",
                modality="text",
                kind="user_claim",
                source_id="test-only",
                observation="Test-only claim",
            )
        ],
    )
    schema = for_case(case)
    proposed = Proposal(
        hypotheses=[
            candidate("test-only", "Insufficient lubrication", ["known-test-source"])
        ],
        follow_up_queries=[],
        unresolved=[],
    ).model_dump()
    assert schema.model_validate(proposed)
    proposed["hypotheses"][0]["supporting_evidence_ids"] = ["invented-test-source"]
    try:
        schema.model_validate(proposed)
    except ValidationError:
        return
    raise AssertionError(
        "Unknown source ID was accepted by constrained decoding schema"
    )
