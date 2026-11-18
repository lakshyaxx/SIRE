"""Versioned case retrieval with explicit trust, temporal availability and overlap scoring."""

import json
import uuid
from app.storage.database import now
from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.simulation.repository import utc


def _asset_readings(case: dict) -> dict[str, dict]:
    """Return bounded saved channel summaries for the case's exact target asset."""
    for summary in case.get("summaries", []):
        if summary.get("asset_id") == case.get("asset_id"):
            return {
                channel: {
                    key: row.get(key)
                    for key in ["recent_mean", "delta", "unit", "evidence_id"]
                }
                for channel, row in summary.get("channels", {}).items()
                if row.get("available") and row.get("recent_mean") is not None
            }
    return {}


def _comparison_details(selected: dict, other: dict) -> dict:
    """Describe measured trend overlap and reading differences without causal inference."""
    selected_readings = _asset_readings(selected)
    other_readings = _asset_readings(other)
    common = sorted(set(selected_readings) & set(other_readings))

    def direction(value: object) -> int:
        if not isinstance(value, (int, float)) or value == 0:
            return 0
        return 1 if value > 0 else -1

    overlapping = [
        {
            "channel": channel,
            "direction": "increasing"
            if direction(selected_readings[channel]["delta"]) > 0
            else "decreasing"
            if direction(selected_readings[channel]["delta"]) < 0
            else "stable",
        }
        for channel in common
        if isinstance(selected_readings[channel]["delta"], (int, float))
        and isinstance(other_readings[channel]["delta"], (int, float))
        if direction(selected_readings[channel]["delta"])
        == direction(other_readings[channel]["delta"])
    ]
    differences = [
        {
            "channel": channel,
            "selected_value": selected_readings[channel]["recent_mean"],
            "prior_value": other_readings[channel]["recent_mean"],
            "unit": selected_readings[channel]["unit"],
        }
        for channel in common
        if selected_readings[channel]["unit"] == other_readings[channel]["unit"]
        and selected_readings[channel]["recent_mean"]
        != other_readings[channel]["recent_mean"]
    ]
    return {
        "overlapping_symptoms": overlapping,
        "differing_readings": differences,
        "asset_context": {
            "selected": {
                "scenario_id": selected.get("scenario_id"),
                "asset_id": selected.get("asset_id"),
                "as_of": selected.get("as_of"),
            },
            "prior": {
                "scenario_id": other.get("scenario_id"),
                "asset_id": other.get("asset_id"),
                "as_of": other.get("as_of"),
            },
        },
    }


def similar_cases(ledger: Ledger, case_id: str, as_of: str | None = None) -> list[dict]:
    """Compare canonical supported-mechanism sets; precedent never becomes source measurement."""
    selected = ledger.get("cases", case_id)
    keys = set(selected["possible_contributors"])
    result = []
    for row in ledger.store.rows(
        "SELECT payload FROM v3_cases ORDER BY created_at DESC LIMIT 100"
    ):
        case = json.loads(row["payload"])
        if case["id"] == case_id or (
            as_of and (case["as_of"] > utc(as_of) or case["created_at"] > utc(as_of))
        ):
            continue
        other = set(case["possible_contributors"])
        union = keys | other
        score = len(keys & other) / len(union) if union else 0
        details = _comparison_details(selected, case)
        result.append(
            {
                "case_id": case["id"],
                "asset_id": case["asset_id"],
                "confirmation_status": case["confirmation_status"],
                "overlap_score": score,
                "shared_mechanisms": sorted(keys & other),
                "different_mechanisms": sorted(keys ^ other),
                "source_type": case["source_type"],
                "evidence_ids": case["evidence_ids"],
                "evidence_strength": "provisional_only",
                "provisional": True,
                "retrieval_reason": (
                    f"Shared {len(keys & other)} of {len(union)} distinct provisional mechanisms; ranked by set overlap then case ID."
                ),
                **details,
                "caveat": "Set overlap among provisional rule hypotheses, not calibrated causal similarity.",
            }
        )
    return sorted(result, key=lambda r: (-r["overlap_score"], r["case_id"]))[:10]


def annotations(ledger: Ledger, case_id: str) -> list[dict]:
    """Read append-only human review statements separately from source measurements."""
    ledger.get("cases", case_id)
    return [
        json.loads(r["payload"])
        for r in ledger.store.rows(
            "SELECT payload FROM v3_annotations WHERE case_id=? ORDER BY created_at,id",
            (case_id,),
        )
    ]


def annotate(ledger: Ledger, case_id: str, note: str, review_status: str) -> dict:
    """Record an unverified local user's review; never promote it to measured causal evidence."""
    ledger.get("cases", case_id)
    if (
        review_status not in {"provisional", "human_reviewed_simulation", "superseded"}
        or not note.strip()
        or len(note) > 2000
    ):
        raise SireError(
            "invalid_review",
            "Enter a non-empty bounded review note and allowed status.",
        )
    result = {
        "id": str(uuid.uuid4()),
        "case_id": case_id,
        "note": note,
        "review_status": review_status,
        "created_at": now(),
        "source_type": "manually_entered",
        "authenticity": "unverified_local_user",
        "limitation": "Review status is a human assertion, not proof of a physical cause.",
    }
    with ledger.store.connection() as db:
        db.execute(
            "INSERT INTO v3_annotations VALUES(?,?,?,?)",
            (result["id"], case_id, json.dumps(result), result["created_at"]),
        )
    return result
