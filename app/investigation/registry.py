"""Retain every candidate while selecting bounded active work by recorded evidence ordering."""

from app.evidence.ledger import digest
from app.investigation.identity import POLICY, mechanism_key
from app.investigation.schemas import Case, Hypothesis


def registry_rows(
    case_key: str, candidates: list[Hypothesis], ranked: list[dict], round_id: int
) -> list[dict]:
    """Produce case-specific identities and explicit deferred/rejected states without dropping data."""
    definitions = {item.id: item for item in candidates}
    limit = POLICY["max_candidates"]
    return [
        {
            "case_hypothesis_id": "CASEHYP:" + digest([case_key, row["id"]])[:24],
            "canonical_mechanism_id": row["id"],
            "canonical_key": mechanism_key(row["mechanism"]),
            "definition": definitions[row["id"]].model_dump(),
            "evaluation": row,
            "selection_state": "active" if position < limit else "deferred",
            "selection_rationale": {
                "position": position + 1,
                "active_budget": limit,
                "ranking_score": row["ranking_score"],
                "status": row["status"],
                "policy": "Non-rejected candidates first, then descending evidence heuristic; stable ID breaks ties. No calibrated probability.",
            },
            "last_evaluated_round": round_id,
        }
        for position, row in enumerate(ranked)
    ]


def case_identity(case: Case, previous: dict | None = None) -> str:
    """Keep a revision in its original lineage; unrelated cases have different registry identities."""
    if previous and previous.get("case_key"):
        return previous["case_key"]
    original = previous["case"] if previous else case.model_dump()
    return "CASE:" + digest(
        [
            original["conversation_id"],
            original["question"],
            sorted(item["id"] for item in original["evidence"]),
        ]
    )
