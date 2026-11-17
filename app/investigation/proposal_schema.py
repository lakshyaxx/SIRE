"""Constrain local structured decoding to the exact evidence IDs actually available."""

from enum import Enum
from typing import Annotated
from pydantic import BaseModel, Field, StringConstraints, create_model
from app.investigation.schemas import Case, ExpectedSign, Hypothesis, Proposal
from app.core.config import SETTINGS


def for_case(
    case: Case, references: dict[str, str] | None = None, concise: bool = False
) -> type[BaseModel]:
    """Build a schema whose support/conflict references can only name supplied sources."""
    identifiers = (
        list(references)
        if references is not None
        else list(dict.fromkeys(item.id for item in case.evidence))
    )
    if identifiers:
        reference = Enum(
            "SuppliedEvidenceReference",
            {f"source_{index}": value for index, value in enumerate(identifiers)},
            type=str,
        )
        source_list = list[reference]
        limit = 32
    else:
        source_list = list[str]
        limit = 0
    concise_fields = {}
    short = Annotated[str, StringConstraints(max_length=120)]
    if concise:
        concise_fields = {
            "mechanism": (str, Field(max_length=160)),
            "assumptions": (list[short], Field(max_length=2)),
            "expected_signs": (list[ExpectedSign], Field(max_length=1)),
            "missing_tests": (list[short], Field(max_length=2)),
        }
        limit = min(limit, 6)
    candidate = create_model(
        "SourceConstrainedHypothesis",
        __base__=Hypothesis,
        supporting_evidence_ids=(source_list, Field(max_length=limit)),
        contradicting_evidence_ids=(source_list, Field(max_length=limit)),
        **concise_fields,
    )
    proposal_fields = (
        {
            "follow_up_queries": (list[short], Field(max_length=1)),
            "unresolved": (list[short], Field(max_length=2)),
        }
        if concise
        else {}
    )
    return create_model(
        "SourceConstrainedProposal",
        __base__=Proposal,
        hypotheses=(
            list[candidate],
            Field(
                min_length=0,
                max_length=SETTINGS["investigation_max_candidates"] if concise else 8,
            ),
        ),
        **proposal_fields,
    )


def expand(proposal: BaseModel, references: dict[str, str]) -> Proposal:
    """Restore each schema-validated model alias to the exact source ID before ranking."""
    from app.evidence.context import restore_text

    value = proposal.model_dump(mode="json")
    for candidate in value["hypotheses"]:
        candidate["mechanism"] = restore_text(candidate["mechanism"], references)
        for field in ["assumptions", "missing_tests"]:
            candidate[field] = [
                restore_text(text, references) for text in candidate[field]
            ]
        for sign in candidate["expected_signs"]:
            sign["predicate"] = restore_text(sign["predicate"], references)
        for field in ["supporting_evidence_ids", "contradicting_evidence_ids"]:
            candidate[field] = [
                references[identifier] if identifier in references else identifier
                for identifier in candidate[field]
            ]
    value["unresolved"] = [
        restore_text(text, references) for text in value["unresolved"]
    ]
    value["follow_up_queries"] = [
        restore_text(text, references) for text in value["follow_up_queries"]
    ]
    return Proposal.model_validate(value)
