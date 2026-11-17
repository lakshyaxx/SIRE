"""Observable assertion and limited citation-support checks, never private cause evaluation."""

import json
import math
from pathlib import Path
from statistics import mean
from app.simulation.repository import utc
from scripts.stress_lab.corpus import read_only


def verify_snapshot(record: dict, source: Path, cutoff: str | None) -> dict:
    """Check exact numeric claims against original public rows, not citation syntax alone."""
    evidence = record["evidence"]
    observation = evidence["observation"]
    result = {
        "evidence_id": evidence["id"],
        "exists": True,
        "time_fence": cutoff is None or evidence["available_at"] <= utc(cutoff),
        "semantic_status": "needs_human_review",
        "claim_type": "unreviewed_model_or_document_claim",
        "original_record_ids": [],
    }
    rows = observation.get("rows")
    if not isinstance(rows, list) or not rows:
        if observation.get("source_record_id"):
            result["original_record_ids"] = [observation["source_record_id"]]
            result["claim_type"] = "recorded_event_text"
            with read_only(source) as db:
                pk = {
                    "events": "event_id",
                    "technician_logs": "log_id",
                    "work_orders": "work_order_id",
                    "alarms": "alarm_id",
                    "inspections": "inspection_id",
                }
                found = []
                for table, key in pk.items():
                    found.extend(
                        dict(r)
                        for r in db.execute(
                            f'SELECT * FROM "{table}" WHERE "{key}"=?',
                            (observation["source_record_id"],),
                        )
                    )
            text = observation.get("text", "")
            supported = bool(found) and any(
                any(
                    str(row.get(field, "")) and str(row.get(field, "")) in text
                    for field in ["details", "note", "technician_note", "finding"]
                )
                or (row.get("alarm_id") and str(row["alarm_id"]) in text)
                for row in found
            )
            result["semantic_status"] = (
                "supported_exact_record" if supported else "unsupported"
            )
        return result
    direct = all(
        r.get("source_record_id", "").startswith("telemetry:row:") for r in rows
    )
    if not direct:
        return result
    original_ids = sorted(
        {int(row["source_record_id"].rsplit(":", 1)[1]) for row in rows}
    )
    originals = {}
    with read_only(source) as db:
        for start in range(0, len(original_ids), 800):
            selected = original_ids[start : start + 800]
            for row in db.execute(
                "SELECT rowid AS original_rowid,* FROM telemetry WHERE rowid IN ("
                + ",".join("?" for _ in selected)
                + ")",
                selected,
            ):
                originals[row["original_rowid"]] = dict(row)
    exact = True
    for row in rows:
        raw = originals.get(int(row["source_record_id"].rsplit(":", 1)[1]))
        exact &= (
            bool(raw)
            and raw["asset_id"] == row["asset_id"]
            and utc(raw["timestamp_utc"]) == row["observed_at"]
            and raw[row["source_field"]] == row["value"]
        )
        result["time_fence"] &= (
            cutoff is None
            or row["observed_at"] <= utc(cutoff)
            and row["available_at"] <= utc(cutoff)
        )
    baseline = [
        r["value"]
        for r in rows[:24]
        if r["quality"] == "good" and r["value"] is not None
    ]
    recent = [
        r["value"]
        for r in rows[-6:]
        if r["quality"] == "good" and r["value"] is not None
    ]
    stats = observation.get("statistics", {})
    for key, values in [("baseline_mean", baseline), ("recent_mean", recent)]:
        expected = mean(values) if values else None
        exact &= stats.get(key) == expected
    with read_only(source) as db:
        latest = db.execute(
            "SELECT MAX(timestamp_utc) FROM telemetry WHERE asset_id=? AND timestamp_utc<=?",
            (
                rows[0]["asset_id"],
                utc(cutoff or rows[-1]["observed_at"]).replace("+00:00", "Z"),
            ),
        ).fetchone()[0]
    fresh = latest is not None and rows[-1]["observed_at"] == utc(latest)
    result["latest_visible_sample_included"] = fresh
    exact &= fresh
    if stats.get("available"):
        exact &= math.isclose(
            stats["delta"], mean(recent) - mean(baseline), abs_tol=1e-12
        )
    result.update(
        semantic_status="supported_exact_numeric_claim" if exact else "unsupported",
        claim_type="numeric_statistics_from_original_rows",
        original_record_ids=[f"telemetry:row:{n}" for n in original_ids],
        scope="Exact numeric/source agreement only; does not certify a causal hypothesis citing the same record.",
    )
    return result


def scorecard(results: list[dict]) -> dict:
    """Produce measured denominators; never turn unreviewed claims or unavailable truth into passes."""
    from collections import Counter
    from statistics import median

    executed = [r for r in results if r.get("executed")]
    times = sorted(r["latency_ms"] for r in executed)
    citations = [c for r in executed for c in r.get("citation_checks", [])]
    reviewed = [c for c in citations if c["semantic_status"] != "needs_human_review"]
    supported = [c for c in reviewed if c["semantic_status"].startswith("supported_")]
    return {
        "recorded_tests": len(results),
        "executed_tests": len(executed),
        "by_priority_status": {
            p: dict(Counter(r["assessment"] for r in results if r["priority"] == p))
            for p in ["P0", "P1", "P2"]
        },
        "latency_ms": {
            "count": len(times),
            "p50": median(times) if times else None,
            "p95_nearest_rank": (
                times[max(0, math.ceil(0.95 * len(times)) - 1)] if times else None
            ),
            "scope": "Serial case wall time including public context preparation, uploads, actual tools and validation; not just inference.",
        },
        "source_snapshot_support": {
            "supported": len(supported),
            "checked": len(reviewed),
            "rate": len(supported) / len(reviewed) if reviewed else None,
            "unreviewed": len(citations) - len(reviewed),
            "scope": "Exact saved snapshot statistics/event text matched to original public records. This does not check how a generated answer uses the snapshot; it is not answer-claim entailment.",
        },
        "citation_semantic_support": {
            "supported": 0,
            "checked": 0,
            "rate": None,
            "scope": "Answer-claim entailment requires separate manual review; exact snapshot agreement is reported separately.",
        },
        "future_evidence_violations": sum(not c["time_fence"] for c in citations),
        "future_evidence_checks": len(citations),
        "top1_known_cause": None,
        "top3_known_cause": None,
        "false_positive_rate": None,
        "private_label_evaluation": "Unavailable until a separate offline evaluator reads external private labels after frozen results. No labels are loaded by this runner.",
    }


def save_scorecard(results_path: Path) -> None:
    """Refresh an aggregate from preserved actual results after each completed case."""
    rows = [
        json.loads(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results_path.with_suffix(".scorecard.json").write_text(
        json.dumps(scorecard(rows), indent=2), encoding="utf-8"
    )


def capability_coverage(result: dict, expectations: list[str], mapping: dict) -> dict:
    """Match expected abstract capabilities to actual recorded operations, never imagined tools."""
    actual = set(result.get("tool_calls", []))
    if any(
        c.get("exists") and c.get("snapshot_path")
        for c in result.get("citation_checks", [])
    ):
        actual.add("cache.evidence_resolved")
    for call in result.get("api_calls", []):
        path = call["path"]
        if path == "/attachments":
            actual.add("api.attachments")
        if path.startswith("/evidence/"):
            actual.add("api.evidence")
        if path.startswith("/runs/"):
            actual.add("api.trace")
        if path == "/predictions/models":
            actual.add("api.models")
    for upload in result.get("uploads", []):
        metadata = upload.get("response", {}).get("metadata", {})
        if metadata.get("transcript"):
            actual.add("upload.actual_asr")
        if metadata.get("video", {}).get("decoded_frames"):
            actual.add("upload.actual_frames")
    metadata = result.get("raw_chat", {}).get("metadata", {})
    if metadata.get("orchestration", {}).get("run_id"):
        actual.add("sse.actual_run")
    if metadata.get("context_selection"):
        actual.add("context.reference_validation")
    if len(result.get("turns", [])) > 1:
        actual.add("chat.multiturn")
    if result.get("load_metrics"):
        actual.add("load.actual_measurement")
    return {
        name: (
            {
                "matched_actual_operations": sorted(actual & set(mapping[name])),
                "fulfilled": bool(actual & set(mapping[name])),
            }
            if name in mapping
            else {
                "fulfilled": None,
                "reason": "Suggested capability has no unambiguous implemented mapping; manual assessment required.",
            }
        )
        for name in expectations
    }
