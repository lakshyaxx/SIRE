"""General error isolation and provenance tests. Model fixtures are explicitly test-only."""

import asyncio
import pytest
from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.evidence.measurements import parse
from app.evidence.verification import (
    Claim,
    verify_claim,
    screen_numeric_prose,
    review_numeric_prose,
)
from app.investigation import engine
from app.investigation.schemas import Case, EvidenceItem, Hypothesis, Proposal
from app.orchestration.understanding import target_asset
from app.orchestration.case_context import recall, last_attempt
from app.chat.service import ChatService
from app.investigation.narrative import observation_role_issues
from app.investigation.narrative import review
from app.investigation.schemas import ExpectedSign
from app.evidence.context import restore_text


def test_unknown_attachment_identifiers_cannot_bypass_reference_validation():
    known = "a" * 32
    assert restore_text("A source [" + known + "]", {"E1": known})
    with pytest.raises(SireError):
        restore_text("A source [" + "b" * 32 + "]", {"E1": known})


@pytest.mark.parametrize(
    "rows",
    [
        "UNIT-72,2026-01-01T00:00:00Z,pressure,2,bar\nUNIT-72,2026-01-01T00:00:00Z,pressure,9,bar\n",
        "UNIT-72,2026-01-01T00:00:00Z,pressure,2,bar\nUNIT-72,2026-01-01T01:00:00Z,pressure,200,kPa\n",
        "UNIT-72,2026-01-01T00:00:00,pressure,2,bar\n",
        "UNIT-72,2026-01-01T00:00:00Z,pressure,,bar\n",
    ],
)
def test_ambiguous_or_missing_tall_measurements_fail_explicitly_without_imputation(
    rows,
):
    with pytest.raises(SireError) as result:
        parse(("asset_id,timestamp,channel,value,unit\n" + rows).encode(), ".csv")
    assert result.value.code in {"invalid_measurements", "invalid_timestamp"}


@pytest.mark.parametrize("recover", [True, False])
def test_invalid_json_retries_at_most_once_without_inventing_a_proposal(
    store, monkeypatch, recover
):
    case = reported_case(
        store,
        "Asset ID: UNIT-72. A noise was reported, but nothing has been inspected.",
    )
    calls = []

    async def generate(*args):
        calls.append(args)
        if len(calls) == 1 or not recover:
            raise SireError(
                "llm_invalid_response", "Explicit test-only invalid JSON", 503
            )
        return Proposal(
            hypotheses=[
                candidate(
                    "test-only",
                    "A loose connection may contribute to noise.",
                    case.evidence[0].id,
                )
            ],
            follow_up_queries=[],
            unresolved=[],
        )

    monkeypatch.setattr(engine.ollama, "generate_async", generate)
    if recover:
        result = asyncio.run(engine.investigate(store, case, asyncio.Event()))
        assert result.hypotheses and result.tools[0].generation_attempts == 2
    else:
        with pytest.raises(SireError):
            asyncio.run(engine.investigate(store, case, asyncio.Event()))
    assert len(calls) == 2


def test_two_timestamped_quantities_are_checked_against_their_own_clauses(store):
    case = reported_case(
        store,
        "Pressure was 4 bar at 2026-01-01T01:00:00Z, then 2 bar at 2026-01-01T02:00:00Z.",
    )
    source = case.evidence[0].id
    ledger = Ledger(store)
    checks = screen_numeric_prose(
        f"Reported pressure was 4 bar at 2026-01-01T01:00:00Z, then 2 bar at 2026-01-01T02:00:00Z [{source}].",
        ledger,
    )
    assert all(row["status"] == "supported_contextually" for row in checks)
    assert checks[0]["claim"]["observed_at"] != checks[1]["claim"]["observed_at"]
    with pytest.raises(SireError):
        screen_numeric_prose(
            f"Reported pressure was 4 bar at 2026-01-01T02:00:00Z [{source}].", ledger
        )


def test_nested_note_brackets_and_hyphenated_words_are_not_mistaken_for_citation_ranges():
    mapping = {"E1": "user:" + "a" * 32, "E2": "user:" + "b" * 32}
    note = "[Note: no linkage to C-MAPSS is established; user claims [E1] do not prove cause.]"
    assert mapping["E1"] in restore_text(note, mapping)
    expanded = restore_text("Sources [E1–E2]", mapping)
    assert mapping["E1"] in expanded and mapping["E2"] in expanded
    with pytest.raises(SireError):
        restore_text("[E1-E3]", mapping)
    with pytest.raises(SireError):
        restore_text("[E2-E1]", mapping)


def test_an_assumption_or_expected_test_result_is_not_mistaken_for_an_observation():
    item = EvidenceItem(
        id="test-only",
        source_id="test-only",
        modality="text",
        kind="user_claim",
        observation="Actual coolant level has not been measured.",
    )
    hypothesis = candidate(
        "test-only", "A low coolant level could contribute to overheating.", item.id
    )
    hypothesis.assumptions = ["The actual coolant level is low."]
    hypothesis.expected_signs = [
        ExpectedSign(
            predicate="Coolant level is below normal when measured.",
            expected_value=True,
        )
    ]
    proposal = Proposal(
        hypotheses=[hypothesis],
        follow_up_queries=[],
        unresolved=["No actual coolant level has been measured."],
    )
    assert not review(proposal, [item])
    hypothesis.mechanism = "The actual coolant level is low."
    assert review(
        Proposal(hypotheses=[hypothesis], follow_up_queries=[], unresolved=[]), [item]
    )


@pytest.mark.parametrize("identity", ["FAN-A", "4072", "LINE/A.V2"])
def test_declared_identifiers_are_not_restricted_to_letter_dash_number_codes(identity):
    assert target_asset("Asset ID: " + identity, []) == identity


def test_failed_attempt_is_retained_for_followup_without_inventing_a_completed_case(
    store, provider, monkeypatch
):
    case = reported_case(
        store,
        "Asset ID: UNIT-72. Overheating was reported after service; no readings were supplied.",
    )

    async def unavailable(*args):
        raise SireError(
            "llm_unavailable", "Explicit test-only unavailable provider", 503
        )

    monkeypatch.setattr(engine.ollama, "generate_async", unavailable)

    async def run():
        service = ChatService(store, provider)
        first = [
            e
            async for e in service.events(
                case.conversation_id,
                "test-only-first",
                case.question,
                [],
                "investigate",
                None,
                None,
                False,
            )
        ]
        assert first[-1]["status"] == "error" and not store.rows("SELECT id FROM cases")
        followup = [
            e
            async for e in service.events(
                case.conversation_id,
                "test-only-followup",
                "Explain that investigation in simple words.",
                [],
                "chat",
                None,
                None,
                False,
            )
        ]
        assert (
            followup[-1]["metadata"]["prior_investigation_attempt"]["asset_id"]
            == "UNIT-72"
        )
        assert any(
            e.get("source") == "actual_prior_investigation_status" for e in followup
        )

    asyncio.run(run())
    assert last_attempt(store, case.conversation_id, "OTHER-8") is None


def test_reopened_partial_case_is_not_reported_as_complete(v2client):
    store = v2client.app.state.store
    cid = store.create_conversation()["id"]
    identifier = store.save_result(
        "cases",
        {
            "case": {
                "question": "Test-only partial case",
                "conversation_id": cid,
                "evidence": [],
            },
            "hypotheses": [],
            "quality_issues": [{"reasons": ["Explicit test-only rejection"]}],
        },
        cid,
    )
    response = v2client.get("/api/v1/frontend/investigations/" + identifier)
    assert response.status_code == 200 and response.json()["status"] == "partial"
    assert response.json()["failure"]["code"] == "hypothesis_quality_review"


@pytest.mark.parametrize(
    "source,bad,qualified",
    [
        (
            "Actual reservoir level has not been measured.",
            "The reservoir level was low.",
            "A low reservoir level could contribute, but it has not been measured.",
        ),
        (
            "The fan was commanded ON, but actual running state is unverified.",
            "The fan is running.",
            "The fan was commanded ON; actual operation remains unverified.",
        ),
        (
            "Pressure readings are unavailable.",
            "Missing pressure measurements confirm an internal leak.",
            "Pressure readings are missing and cannot confirm a leak.",
        ),
    ],
)
def test_missing_and_commanded_states_are_not_promoted_to_observed_facts(
    source, bad, qualified
):
    item = EvidenceItem(
        id="test-only",
        source_id="test-only",
        modality="text",
        kind="user_claim",
        observation=source,
    )
    assert observation_role_issues(bad, [item])
    assert not observation_role_issues(qualified, [item])


def reported_case(store, question: str) -> Case:
    """Persist a real test-store user message so every reference resolves normally."""
    cid = store.create_conversation()["id"]
    mid = store.add_message(cid, "user", question)
    evidence = EvidenceItem(
        id="user:" + mid,
        source_id=mid,
        kind="user_claim",
        modality="text",
        observation=question,
        reliability="low",
    )
    return Case(
        question=question,
        conversation_id=cid,
        asset_id=target_asset(question, []),
        asset_identity_source="user_question",
        evidence=[evidence],
    )


def candidate(identifier: str, mechanism: str, evidence_id: str) -> Hypothesis:
    """Build a test-only model proposal, never an operational diagnosis."""
    return Hypothesis(
        id=identifier,
        mechanism=mechanism,
        assumptions=[],
        expected_signs=[],
        supporting_evidence_ids=[evidence_id],
        contradicting_evidence_ids=[],
        missing_tests=["Independent inspection is needed."],
    )


def test_reported_ranges_and_units_are_source_agreement_not_physical_verification(
    store,
):
    case = reported_case(
        store,
        "Hypothetical current rose from 2.1 to 3.4 A; airflow was 90 m3/h. Valve position was 40%.",
    )
    ledger = Ledger(store)
    source = case.evidence[0].id
    checks = screen_numeric_prose(
        f"Reported current rose from 2.1 to 3.4 A and airflow was 90 m³/h; valve position was 40% [{source}].",
        ledger,
    )
    assert len(checks) == 4 and all(
        row["status"] == "supported_contextually" for row in checks
    )
    assert all(row["claim"]["category"] == "reported_observation" for row in checks)
    with pytest.raises(SireError) as rejected:
        screen_numeric_prose(f"Current rose from 900 to 3.4 A [{source}].", ledger)
    assert rejected.value.diagnostics[0]["claim"]["value"] == 900
    assert rejected.value.diagnostics[0]["claim"]["source_ids"] == [source]
    with pytest.raises(SireError):
        screen_numeric_prose(f"Airflow was 90 L/min [{source}].", ledger)


def test_unknown_numeric_frequency_is_not_silently_accepted_and_safe_paragraph_survives(
    store,
):
    result = review_numeric_prose(
        "Independent inspection would distinguish the alternatives.\n\nThe fault is confirmed at 125 Hz.",
        Ledger(store),
    )
    assert (
        result["text"] == "Independent inspection would distinguish the alternatives."
    )
    bad = result["rejected"][0]["verifications"][0]
    assert (
        bad["claim"]["value"] == 125
        and bad["claim"]["unit"] == "Hz"
        and not bad["claim"]["source_ids"]
    )
    assert bad["status"] == "insufficient_evidence"
    assert review_numeric_prose("A frequency of 1e999 Hz was observed.", Ledger(store))[
        "rejected"
    ]


def test_multiple_cited_units_do_not_make_a_valid_point_fail_on_an_unrelated_unit(
    store,
):
    ledger = Ledger(store)
    ids = []
    for channel, value, unit in [("pressure", 4, "bar"), ("temperature", 70, "degC")]:
        ids.append(
            ledger.add(
                "real_uploaded",
                "Test-only source",
                {
                    "rows": [
                        {
                            "asset_id": "UNIT-72",
                            "channel": channel,
                            "value": value,
                            "unit": unit,
                            "observed_at": "2026-01-01T00:00:00Z",
                            "quality": "good",
                        }
                    ]
                },
                {"test_only": True},
                unit=unit,
            ).id
        )
    check = verify_claim(
        Claim(
            category="direct_observation",
            source_ids=ids,
            value=70,
            unit="°C",
            observed_at="2026-01-01T00:00:00Z",
        ),
        ledger,
    )
    assert check.status == "verified_exact"
    assert (
        verify_claim(
            Claim(
                category="direct_observation",
                source_ids=[ids[0]],
                value=4,
                unit="kPa",
                observed_at="2026-01-01T00:00:00Z",
            ),
            ledger,
        ).status
        == "contradicted"
    )


@pytest.mark.parametrize(
    "name,records",
    [
        (
            "VEHICLE-72",
            "Service record SERVICE-82 and technician note NOTE-51 disagree.",
        ),
        ("PRESS-62", "Maintenance report REPORT-39 is supplied."),
        ("FAN-18", "Inspection ticket TICKET-4 is unverified."),
    ],
)
def test_explicit_asset_identity_is_not_erased_by_other_record_identifiers(
    name, records
):
    question = f"Investigate the equipment named {name}. Asset ID: {name}. {records}"
    assert target_asset(question, []) == name
    assert target_asset("Asset ID: UNIT-1; Asset ID: UNIT-2", []) is None


def test_legacy_case_identity_is_recovered_in_memory_and_named_older_case_is_found(
    store,
):
    cid = store.create_conversation()["id"]
    original = {
        "case": {
            "question": "Investigate vehicle named VEHICLE-72. Work order JOB-4 conflicts with NOTE-5.",
            "conversation_id": cid,
            "asset_id": None,
            "evidence": [],
        },
        "hypotheses": [],
    }
    first = store.save_result("cases", original, cid)
    store.save_result(
        "cases",
        {
            "case": {
                "question": "Investigate UNIT-9",
                "asset_id": "UNIT-9",
                "evidence": [],
            },
            "hypotheses": [],
        },
        cid,
    )
    found = recall(store, cid, "VEHICLE-72")
    assert (
        found["case_id"] == first and found["case"]["case"]["asset_id"] == "VEHICLE-72"
    )
    assert store.result("cases", first)["case"]["asset_id"] is None
    assert recall(store, cid, "OTHER-8") is None


def test_one_numeric_candidate_does_not_destroy_other_candidates(store, monkeypatch):
    case = reported_case(
        store,
        "Asset ID: UNIT-72. The reported pressure fell from 5.2 to 4.4 bar; inspection has not confirmed a cause.",
    )
    good = candidate(
        "valid", "A restriction may explain the reported change.", case.evidence[0].id
    )
    bad = candidate("invalid", "Pressure was measured at 999 bar.", case.evidence[0].id)

    async def generate(*args):
        return Proposal(hypotheses=[good, bad], follow_up_queries=[], unresolved=[])

    monkeypatch.setattr(engine.ollama, "generate_async", generate)
    result = asyncio.run(engine.investigate(store, case, asyncio.Event()))
    assert len(result.hypotheses) == 1 and result.quality_issues
    numeric = next(
        r for r in result.quality_issues if r.get("code") == "unsupported_numeric_claim"
    )
    assert numeric["verification"][0]["claim"]["value"] == 999
    assert (
        result.case.asset_id == "UNIT-72"
        and result.hypotheses[0]["status"] == "tentative"
    )


def test_an_invented_threshold_in_a_diagnostic_field_is_also_rejected(
    store, monkeypatch
):
    case = reported_case(
        store, "Test-only: noise and heat were reported; no spectrum exists."
    )
    bad = candidate("bad", "A loose mount may explain the noise.", case.evidence[0].id)
    bad.missing_tests = ["Check whether a 125 Hz peak is present."]

    async def generate(*args):
        return Proposal(hypotheses=[bad], follow_up_queries=[], unresolved=[])

    monkeypatch.setattr(engine.ollama, "generate_async", generate)
    result = asyncio.run(engine.investigate(store, case, asyncio.Event()))
    assert (
        not result.hypotheses
        and result.quality_issues[0]["code"] == "unsupported_numeric_claim"
    )


def test_failed_repair_keeps_valid_completed_draft_and_is_bounded(store, monkeypatch):
    case = reported_case(store, "Test-only hypothetical vibration report")
    calls = []

    async def generate(*args):
        calls.append(args)
        if len(calls) == 1:
            return Proposal(
                hypotheses=[
                    candidate(
                        "valid",
                        "A loose mount may explain the vibration.",
                        case.evidence[0].id,
                    ),
                    candidate("bad", "The effect is not", case.evidence[0].id),
                ],
                follow_up_queries=[],
                unresolved=[],
            )
        raise SireError(
            "llm_invalid_response", "Explicit test-only malformed repair", 503
        )

    monkeypatch.setattr(engine.ollama, "generate_async", generate)
    result = asyncio.run(engine.investigate(store, case, asyncio.Event()))
    assert (
        len(calls) == 2
        and len(result.hypotheses) == 1
        and result.followup_error["code"] == "llm_invalid_response"
    )
    assert result.hypotheses[0]["mechanism"].startswith("A loose mount")


@pytest.mark.parametrize(
    "question",
    [
        "Asset ID: BLOWER-26. A cleaning record says completed; a later technician note says deferred. Airflow is reduced and vibration is reported; neither record is verified.",
        "Asset ID: WATER-32. Reported temperature rose from 51 to 67 °C while vibration increased. Pressure measurements are unavailable.",
        "Asset ID: VEHICLE-72. Overheating began after coolant service. Heater air is intermittently cold. Coolant level was not measured; fan was commanded ON but physical operation is unverified.",
        "Asset ID: PRESS-62. Motion is slow and pressure fluctuates. Internal bypass is suspected but reservoir level has not been measured and no external loss is established.",
        "Asset ID: DRIVE-18. Motor current rose from 4.1 to 5.3 A and a rattling sound was reported. No spectrum or winding test is available.",
        "Asset ID: SHAFT-29. A rattling noise was reported. No numeric readings or confirmed inspection findings exist.",
    ],
)
def test_diverse_reported_inputs_keep_case_scope_and_unconfirmed_status(
    store, monkeypatch, question
):
    case = reported_case(store, question)

    async def generate(*args):
        return Proposal(
            hypotheses=[
                candidate(
                    "test-only",
                    "A mechanical change may contribute; independent inspection is needed.",
                    case.evidence[0].id,
                )
            ],
            follow_up_queries=[],
            unresolved=["Independent observations are needed."],
        )

    monkeypatch.setattr(engine.ollama, "generate_async", generate)
    result = asyncio.run(engine.investigate(store, case, asyncio.Event()))
    assert (
        result.case.asset_id == case.asset_id
        and result.hypotheses[0]["status"] == "tentative"
    )
    assert (
        result.hypotheses[0]["evidence_support"] == "low"
        and not result.hypotheses[0]["falsified_by"]
    )


def test_safe_commentary_is_retained_when_another_paragraph_invents_a_quantity(
    store, provider
):
    cid = store.create_conversation()["id"]

    async def stream(*args):
        yield "The alternatives need independent evidence.\n\nThe measured frequency was 123 Hz."

    provider.stream = stream

    async def run():
        return [
            e
            async for e in ChatService(store, provider).events(
                cid,
                "test-only",
                "Explain the possible sensor issue",
                [],
                "chat",
                None,
                None,
                False,
            )
        ]

    events = asyncio.run(run())
    done = events[-1]
    assert (
        done["status"] == "partial"
        and done["metadata"]["error"]["code"] == "unsupported_numeric_claim"
    )
    assert "123 Hz" not in "".join(e.get("text", "") for e in events)
    assert (
        done["metadata"]["rejected_commentary"][0]["verifications"][0]["claim"]["value"]
        == 123
    )
