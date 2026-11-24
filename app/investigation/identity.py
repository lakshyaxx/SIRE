"""Conservative stable hypothesis identity, explicit duplicate merging and ambiguity retention."""

from collections import defaultdict
import re
import yaml
from app.core.config import ROOT
from app.evidence.ledger import digest
from app.investigation.schemas import Hypothesis, ExpectedSign

POLICY = yaml.safe_load((ROOT / "config/hypotheses.yaml").read_text(encoding="utf-8"))


def mechanism_key(mechanism: str) -> str:
    """Normalize lexical identity and explicit aliases without claiming general semantic equivalence."""
    normalized = " ".join(re.findall(r"[a-z0-9]+", mechanism.casefold()))
    for canonical, aliases in POLICY["aliases"].items():
        if normalized in aliases:
            return canonical
    return (
        " ".join(
            word
            for word in normalized.split()
            if word not in POLICY["ignore_identity_words"]
        )
        or normalized
    )


def merge(candidates: list[Hypothesis]) -> tuple[list[Hypothesis], list[dict]]:
    """Merge only matching canonical mechanisms, preserving conflicting relationship checks."""
    groups = defaultdict(list)
    for candidate in candidates:
        groups[mechanism_key(candidate.mechanism)].append(candidate)
    result, records = [], []
    for key, items in groups.items():
        support = {value for item in items for value in item.supporting_evidence_ids}
        conflict = {
            value for item in items for value in item.contradicting_evidence_ids
        }
        ambiguous = support & conflict
        signs = defaultdict(set)
        for item in items:
            for sign in item.expected_signs:
                signs[sign.predicate].add(sign.expected_value)
        disputed = [predicate for predicate, values in signs.items() if len(values) > 1]
        missing = list(
            dict.fromkeys(value for item in items for value in item.missing_tests)
        )
        if ambiguous:
            missing.append(
                "Verify ambiguous support/conflict relationship for source(s): "
                + ", ".join(sorted(ambiguous))
            )
        if disputed:
            missing.append(
                "Clarify inconsistent proposed prerequisites: "
                + ", ".join(sorted(disputed))
            )
        identifier = "HYP:" + digest(key)[:16]
        result.append(
            Hypothesis(
                id=identifier,
                mechanism=items[-1].mechanism,
                assumptions=list(
                    dict.fromkeys(value for item in items for value in item.assumptions)
                )[:8],
                expected_signs=[
                    ExpectedSign(predicate=predicate, expected_value=next(iter(values)))
                    for predicate, values in sorted(signs.items())
                    if len(values) == 1
                ][:8],
                supporting_evidence_ids=sorted(support - ambiguous)[:32],
                contradicting_evidence_ids=sorted(conflict - ambiguous)[:32],
                missing_tests=missing[:8],
            )
        )
        records.append(
            {
                "hypothesis_id": identifier,
                "canonical_key": key,
                "proposal_ids": sorted({item.id for item in items}),
                "merged_count": len(items),
                "ambiguous_source_ids": sorted(ambiguous),
                "disputed_prerequisites": sorted(disputed),
            }
        )
    return result, records
