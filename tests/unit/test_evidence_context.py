"""Model context compression retains real references and refuses invented citations."""

import pytest
from app.evidence.context import compact, restore_text
from app.core.errors import SireError
from app.investigation.schemas import EvidenceItem
from app.investigation.proposal_schema import for_case, expand
from app.investigation.schemas import Case


def test_short_source_aliases_roundtrip_to_exact_canonical_records():
    identifier = "EV:" + "a" * 64
    items = [
        EvidenceItem(
            id=identifier,
            source_id="test-only-image",
            kind="model_inference",
            modality="image",
            observation="Test-only pixel observation",
        )
    ]
    context, mapping = compact(items, "Test-only question")
    assert context["untrusted_evidence"][0]["id"] == "E1" and identifier not in str(
        context
    )
    assert restore_text("Test-only observation [e1]", mapping).endswith(
        "[" + identifier + "]"
    )
    assert restore_text("Sources [E1, E1]", mapping).count(identifier) == 2
    with pytest.raises(SireError, match="unknown"):
        restore_text("Claim [E99]", mapping)
    schema = for_case(
        Case(question="test-only", conversation_id="test-only", evidence=items), mapping
    )
    proposal = schema.model_validate(
        {
            "hypotheses": [
                {
                    "id": "test-only-h",
                    "mechanism": "Test-only possible cause",
                    "assumptions": [],
                    "expected_signs": [],
                    "supporting_evidence_ids": ["E1"],
                    "contradicting_evidence_ids": [],
                    "missing_tests": [],
                }
            ],
            "follow_up_queries": [],
            "unresolved": [],
        }
    )
    assert expand(proposal, mapping).hypotheses[0].supporting_evidence_ids == [
        identifier
    ]


def test_context_budget_records_omission_and_unknown_canonical_ref_is_withheld():
    item = EvidenceItem(
        id="EV:" + "a" * 64,
        source_id="test-only",
        kind="user_claim",
        modality="text",
        observation="Test-only " * 1000,
    )
    context, mapping = compact([item], "Test-only", budget=50)
    assert not mapping and context["selection"]["omitted_sources"] == 1
    with pytest.raises(SireError, match="not supplied"):
        restore_text("Unsupported [EV:" + "b" * 64 + "]", {})


def test_many_measurement_channels_cannot_crowd_out_an_independent_document():
    rows = [
        EvidenceItem(
            id=f"test-channel-{n}",
            source_id="test-csv",
            kind="measurement",
            modality="uploaded_measurements",
            observation="Test-only reading " * 80,
        )
        for n in range(12)
    ]
    rows.append(
        EvidenceItem(
            id="test-document",
            source_id="test-pdf",
            kind="document_guidance",
            modality="document",
            observation="Test-only inspection guidance",
        )
    )
    context, mapping = compact(rows, "Test-only question", budget=3500)
    assert "test-document" in mapping.values()
    assert context["selection"]["omitted_sources"] > 0


def test_bounded_excerpts_preserve_both_short_conflicting_document_accounts():
    """A long manual and many channels must leave room for the second account."""
    rows = [
        EvidenceItem(
            id=f"test-channel-{n}",
            source_id="test-csv",
            kind="measurement",
            modality="uploaded_measurements",
            observation="Test-only long measurement context " * 80,
        )
        for n in range(12)
    ]
    rows.extend(
        [
            EvidenceItem(
                id="test-manual",
                source_id="test-manual",
                kind="document_guidance",
                modality="document",
                observation="Test-only long manual context " * 80,
            ),
            *[
                EvidenceItem(
                    id=f"test-account-{n}",
                    source_id="test-handover",
                    kind="document_guidance",
                    modality="document",
                    observation=text,
                )
                for n, text in enumerate(
                    [
                        "Test-only account: maintenance was completed.",
                        "Test-only account: maintenance was deferred.",
                    ]
                )
            ],
        ]
    )
    context, mapping = compact(
        rows,
        "Compare the conflicting maintenance accounts.",
        budget=3500,
        observation_characters=500,
    )
    assert {"test-account-0", "test-account-1"} <= set(mapping.values())
    assert context["selection"]["excerpted_sources"]
    assert all(
        len(item["observation"]) <= 500 for item in context["untrusted_evidence"]
    )
