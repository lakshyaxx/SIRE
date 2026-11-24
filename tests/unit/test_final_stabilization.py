"""Regression controls for observed incomplete prose, source confusion and topic loss."""

import asyncio
import pytest
from app.chat.conversation import fast_route, describe
from app.evidence.context import compact
from app.evidence.measurements import profile
from app.evidence.inventory import review_recommendations
from app.investigation import engine
from app.investigation.narrative import issues, evidence_issues, review
from app.investigation.schemas import Case, EvidenceItem, Hypothesis, Proposal
from app.knowledge.ingestion import ingest
from app.orchestration.planner import investigation_requested
from app.chat.service import ChatService
import json


@pytest.mark.parametrize(
    "text", ["The effect is not ", "The conflict may affect a", "Wear of 潤"]
)
def test_observed_incomplete_or_drifted_text_is_withheld(text):
    assert issues(text)


def test_maintenance_check_does_not_establish_analysis_report_existence():
    evidence = [
        EvidenceItem(
            id="test-only",
            modality="user_claim",
            kind="user_claim",
            source_id="test-only",
            observation="Lubrication checked 10 days ago, but no lubricant-analysis report is available.",
            reliability="low",
        )
    ]
    assert evidence_issues(
        "Lubricant analysis report (available 10 days ago, not provided)", evidence
    )
    assert not evidence_issues("No lubricant-analysis report is available.", evidence)
    assert not evidence_issues(
        "Check whether a lubricant analysis report is available.", evidence
    )
    assert evidence_issues("Bearing wear causes pressure loss.", evidence)
    assert evidence_issues(
        "Bearing wear causes pressure loss. The motor current may rise.", evidence
    )
    assert evidence_issues(
        "Bearing friction increases. This friction reduces flow due to internal resistance. It remains unconfirmed.",
        evidence,
    )
    assert evidence_issues(
        "Lubricant analysis report from the 10-day maintenance check", evidence
    )
    assert evidence_issues(
        "Lubrication is not the primary cause given no lubricant analysis report is available.",
        evidence,
    )
    assert not evidence_issues(
        "Bearing wear could contribute to pressure loss; the linkage requires confirmation.",
        evidence,
    )


def test_project_topic_survives_completed_documented_followups(store):
    history = []
    for question in [
        "What is hypothesis engine?",
        "In this project",
        "Explain it simply",
        "How does it work?",
        "Give me an example",
    ]:
        assert fast_route(question, history) == "hypotheses"
        text, record = describe(store, "hypotheses", question)
        assert text and record.modality == "application_documentation"
        history.extend(
            [
                {
                    "role": "user",
                    "status": "complete",
                    "content": question,
                    "metadata": {},
                },
                {
                    "role": "assistant",
                    "status": "complete",
                    "content": text,
                    "metadata": {"response_topic": "hypotheses"},
                },
            ]
        )
    assert fast_route("Investigate PUMP-101 bearing heat", history) is None


def test_general_causal_questions_and_references_do_not_start_new_investigations():
    assert not investigation_requested(
        "Why might a centrifugal pump vibrate at constant speed?"
    )
    assert not investigation_requested(
        "What evidence from our last investigation would change that?"
    )
    assert investigation_requested("Investigate PUMP-101 increasing vibration")
    assert investigation_requested("Why does PUMP-101 vibrate more?")


def test_contextual_model_turn_keeps_saved_asset_and_does_not_borrow_another(
    store, provider
):
    cid = store.create_conversation()["id"]
    claim = store.add_message(cid, "user", "Test-only hypothetical heat report")
    store.save_result(
        "cases",
        {
            "case": {
                "question": "Test-only reported heat",
                "asset_id": "TEST-777",
                "evidence": [
                    EvidenceItem(
                        id="user:" + claim,
                        source_id=claim,
                        kind="user_claim",
                        modality="text",
                        observation="Test-only hypothetical heat report",
                        reliability="low",
                    ).model_dump()
                ],
            },
            "hypotheses": [
                {
                    "mechanism": "Test-only friction may contribute.",
                    "status": "tentative",
                    "missing_tests": ["Test-only independent inspection"],
                }
            ],
        },
        cid,
    )

    async def run():
        service = ChatService(store, provider)
        for rid, question in [
            ("context", "Could you explain that possibility using an analogy?"),
            ("other", "Explain the readings for OTHER-888"),
        ]:
            events = [
                event
                async for event in service.events(
                    cid, rid, question, [], "chat", None, None, False
                )
            ]
            if rid == "context":
                assert (
                    events[-1]["metadata"]["active_case_context"]["asset_id"]
                    == "TEST-777"
                )
                assert "Test-only friction" in json.dumps(provider.requests[-1])
                assert events[-1]["metadata"]["evidence"][0]["id"] == "user:" + claim
                assert any(
                    event["type"] == "evidence"
                    and event["evidence"]
                    and event["evidence"][0]["id"] == "user:" + claim
                    for event in events
                )
            else:
                assert "active_case_context" not in events[-1]["metadata"]

    asyncio.run(run())


def test_only_user_claim_is_citable_but_stays_provisional():
    item = EvidenceItem(
        id="test-only",
        source_id="user",
        kind="user_claim",
        modality="text",
        observation="Test-only hypothetical vibration increase",
        reliability="low",
    )
    context, refs = compact([item], item.observation)
    assert refs == {"E1": "test-only"}
    assert "hypothetical" in str(context)


def test_assumption_language_and_unsupported_stability_are_reviewed():
    item = EvidenceItem(
        id="test-only",
        source_id="test-only",
        kind="measurement",
        modality="uploaded_measurements",
        observation='{"channel":"bearing_temp","delta":12.03}',
        reliability="medium",
    )
    assert evidence_issues("Bearing temperature remains stable.", [item])
    assert not evidence_issues(
        "Bearing temperature increased across the windows.", [item]
    )
    proposal = Proposal(
        hypotheses=[
            Hypothesis(
                id="test-only",
                mechanism="Bearing friction may contribute to heat.",
                assumptions=["Wear in the 吸入"],
                expected_signs=[],
                supporting_evidence_ids=[],
                contradicting_evidence_ids=[],
                missing_tests=[],
            )
        ],
        follow_up_queries=[],
        unresolved=[],
    )
    assert review(proposal, [item])["test-only"]


def test_all_explicit_fan_channels_and_missing_timestamp_are_retained(store):
    cid = store.create_conversation()["id"]
    content = b"asset_id,timestamp_utc,vibration_mm_s_rms,bearing_temp_c,airflow_m3_h,motor_current_a,fan_speed_rpm,inlet_filter_dp_kpa\nTEST-777,2026-01-01T00:00:00Z,1,40,100,2,1200,0.5\nTEST-777,2026-01-01T01:00:00Z,,42,90,3,1201,0.7\n"
    upload = ingest(store, cid, "test-only-fan.csv", content)
    result = profile(store, cid, upload["id"])
    assert len(result["groups"]) == 6
    assert sum(row["count"] for row in result["groups"]) == 11
    vibration = next(row for row in result["groups"] if row["channel"] == "vibration")
    assert vibration["count"] == 1 and vibration["missing_count"] == 1
    assert vibration["missing_timestamps"] == ["2026-01-01T01:00:00+00:00"]
    assert vibration["baseline_mean"] == 1


def test_existing_channel_recommendation_is_qualified_without_borrowing_other_asset():
    available = [
        {
            "asset_id": "TEST-777",
            "channel": "motor_current",
            "unit": "A",
            "evidence_id": "test-only",
            "good_count": 2,
        }
    ]
    texts, checks = review_recommendations(
        ["Review motor current", "Review motor current for OTHER-888"],
        available,
        "TEST-777",
    )
    assert texts[0].startswith("Interpret supplied readings") and len(checks) == 1
    assert texts[1] == "Review motor current for OTHER-888"


def test_quality_retry_is_bounded_and_uses_original_sources(monkeypatch):
    calls = []

    async def generate(messages, *args):
        calls.append(messages)
        return Proposal(
            hypotheses=[
                Hypothesis(
                    id="test-only",
                    mechanism=(
                        "The effect is not"
                        if len(calls) == 1
                        else "Test-only bearing friction may explain the heat."
                    ),
                    assumptions=[],
                    expected_signs=[],
                    supporting_evidence_ids=[],
                    contradicting_evidence_ids=[],
                    missing_tests=[],
                )
            ],
            follow_up_queries=[],
            unresolved=[],
        )

    monkeypatch.setattr(engine.ollama, "generate_async", generate)
    result, review, attempts = asyncio.run(
        engine._reviewed_proposal(
            [{"role": "user", "content": "original test-only source"}],
            Case(conversation_id="test-only", question="Test-only", evidence=[]),
            {},
            asyncio.Event(),
            5,
        )
    )
    assert attempts == 2 and not review and len(calls) == 2
    assert calls[1][0]["content"] == "original test-only source"
    assert result.hypotheses[0].mechanism.endswith("heat.")


def test_multi_asset_measurements_require_selection_and_do_not_enter_wrong_prompt(
    store, monkeypatch
):
    cid = store.create_conversation()["id"]
    upload = ingest(
        store,
        cid,
        "test-only-multiple.csv",
        b"asset_id,timestamp_utc,vibration_mm_s\nTEST-777,2026-01-01T00:00:00Z,1\nOTHER-888,2026-01-01T00:00:00Z,99\n",
    )
    groups = profile(store, cid, upload["id"])["groups"]
    evidence = [
        EvidenceItem(
            id=row["evidence_id"],
            source_id=upload["id"],
            modality="uploaded_measurements",
            kind="measurement",
            asset_identity=row["asset_id"],
            observation=row["asset_id"] + " source readings",
            reliability="medium",
        )
        for row in groups
    ]
    case = Case(
        conversation_id=cid, question="Test-only investigation", evidence=evidence
    )
    result = asyncio.run(engine.investigate(store, case, asyncio.Event()))
    assert result.stop_reason == "asset_scope_ambiguous" and not result.hypotheses
    calls = []

    async def generate(messages, *args):
        calls.append(messages)
        return Proposal(
            hypotheses=[],
            follow_up_queries=[],
            unresolved=["Independent inspection is needed."],
        )

    monkeypatch.setattr(engine.ollama, "generate_async", generate)
    case.asset_id = "TEST-777"
    asyncio.run(engine.investigate(store, case, asyncio.Event()))
    assert calls and "OTHER-888" not in str(calls)
