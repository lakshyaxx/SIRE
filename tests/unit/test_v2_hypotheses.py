"""Falsification rules on explicitly synthetic test evidence, not diagnostic accuracy."""

import asyncio
import pytest
from app.core.errors import SireError
from app.investigation.engine import rank_hypotheses, investigate
from app.investigation.schemas import (
    Case,
    EvidenceItem,
    Hypothesis,
    ExpectedSign,
    Proposal,
)

pytestmark = pytest.mark.usefixtures("sync_proposal_transport")


def proposal(identifier="h1", support=None, conflict=None):
    return Hypothesis(
        id=identifier,
        mechanism="Test-only corrosion mechanism",
        assumptions=[],
        expected_signs=[
            ExpectedSign(predicate="surface_corrosion", expected_value=True)
        ],
        supporting_evidence_ids=support or [],
        contradicting_evidence_ids=conflict or [],
        missing_tests=["test-only inspection"],
    )


def test_reliable_measured_contradiction_can_reject():
    evidence = EvidenceItem(
        id="e1",
        modality="inspection",
        kind="measurement",
        source_id="test-only-fixture",
        observation="Synthetic qualified inspection found no corrosion",
        predicate="surface_corrosion",
        value=False,
        reliability="high",
    )
    case = Case(question="test", conversation_id="test", evidence=[evidence])
    ranked = rank_hypotheses(case, [proposal(conflict=["e1"]), proposal("h2")])
    row = next(x for x in ranked if x["id"] == "h1")
    assert row["status"] == "rejected" and row["falsified_by"] == ["e1"]


def test_confident_user_claim_cannot_reject():
    e = EvidenceItem(
        id="e1",
        modality="user",
        kind="user_claim",
        source_id="test-only",
        observation="Definitely no corrosion",
        reliability="low",
        predicate="surface_corrosion",
        value=False,
    )
    c = Case(question="test", conversation_id="test", evidence=[e])
    assert rank_hypotheses(c, [proposal(conflict=["e1"])])[0]["status"] == "tentative"


def test_fake_or_self_conflicting_sources_refused():
    c = Case(question="test", conversation_id="test", evidence=[])
    with pytest.raises(SireError):
        rank_hypotheses(c, [proposal(support=["invented"])])


def test_linkage_is_not_inferred_from_unrelated_sources():
    c = Case(question="test", conversation_id="test", evidence=[])
    assert not c.linked_asset
    assert rank_hypotheses(c, [proposal()])[0]["evidence_support"] == "low"


def test_loop_deduplicates_and_stops_without_new_document_evidence(store, monkeypatch):
    from app.providers import ollama

    calls = []

    def generate(*args):
        calls.append(args)
        return Proposal(
            hypotheses=[proposal(), proposal("h2")],
            follow_up_queries=["test-only corrosion search"],
            unresolved=["Missing physical inspection"],
        )

    monkeypatch.setattr(ollama, "generate", generate)
    c = store.create_conversation()
    report = asyncio.run(
        investigate(
            store,
            Case(question="test", conversation_id=c["id"], evidence=[]),
            asyncio.Event(),
        )
    )
    assert report.rounds == 1 and len(calls) == 1
    assert len(report.hypotheses) == 1
    assert report.hypothesis_revisions[0]["merges"][0]["merged_count"] == 2
    assert report.stop_reason == "no_new_evidence"


@pytest.mark.parametrize(
    "linked,image_asset,sensor_asset,excluded",
    [
        (False, None, "NASA:FD003:1", True),
        (True, None, "NASA:FD003:1", True),
        (True, "photo-bearing", "NASA:FD003:1", True),
        (True, "verified-test-asset", "verified-test-asset", False),
    ],
)
def test_sensor_support_requires_credible_matching_image_identity(
    linked, image_asset, sensor_asset, excluded
):
    image = EvidenceItem(
        id="image",
        modality="image",
        kind="model_inference",
        source_id="test-only",
        observation="Synthetic test image observation",
        asset_identity=image_asset,
    )
    sensor = EvidenceItem(
        id="sensor",
        modality="sensor_model",
        kind="model_inference",
        source_id="test-only",
        observation="Synthetic test sensor inference",
        asset_identity=sensor_asset,
        reliability="medium",
    )
    case = Case(
        question="test",
        conversation_id="test",
        evidence=[image, sensor],
        linked_asset=linked,
    )
    ranked = rank_hypotheses(case, [proposal(support=["sensor"])])[0]
    assert ranked["excluded_as_unlinked"] == (["sensor"] if excluded else [])
    assert (ranked["ranking_score"] == 0) == excluded
    assert ranked["status"] == "tentative"


def test_duplicate_hypothesis_ids_are_refused():
    case = Case(question="test", conversation_id="test", evidence=[])
    with pytest.raises(SireError, match="unique"):
        rank_hypotheses(case, [proposal(), proposal()])


def test_investigation_has_real_wall_clock_budget(store, monkeypatch):
    import time
    from app.investigation import engine

    def delayed(*args):
        time.sleep(0.05)
        return Proposal(
            hypotheses=[proposal(), proposal("h2")], follow_up_queries=[], unresolved=[]
        )

    monkeypatch.setattr(engine.ollama, "generate", delayed)
    monkeypatch.setitem(engine.SETTINGS, "investigation_budget_seconds", 0.005)
    c = store.create_conversation()
    with pytest.raises(SireError, match="time budget"):
        asyncio.run(
            investigate(
                store,
                Case(question="test", conversation_id=c["id"], evidence=[]),
                asyncio.Event(),
            )
        )
