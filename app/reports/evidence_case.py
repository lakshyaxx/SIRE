"""Traceable exports for actual uploaded-evidence investigations, with no simulated-plant relabeling."""

import json
from app.evidence.ledger import Ledger, digest
from app.storage.database import now


def source_summary(record: dict) -> dict:
    """Keep readable exact previews; the complete unchanged snapshot stays in the JSON audit."""
    observation = dict(record["observation"])
    rows = observation.pop("rows", None)
    if isinstance(rows, list):
        observation["source_rows"] = {
            "count": len(rows),
            "first": rows[:1],
            "last": rows[-1:],
            "scope": "Preview only; download the full JSON audit for every original row",
        }
    for key, value in list(observation.items()):
        if isinstance(value, str) and len(value) > 1200:
            observation[key] = {
                "excerpt": value[:1200],
                "truncated": True,
                "original_characters": len(value),
            }
    return observation


def create(ledger: Ledger, case_id: str) -> dict:
    """Freeze an existing general case and exact sources into a genuine report snapshot."""
    saved = ledger.store.result("cases", case_id)
    evidence = [ledger.resolve(item["id"]) for item in saved["case"]["evidence"]]
    signature = digest(
        {
            "case": saved,
            "evidence": evidence,
            "format": "sire-uploaded-evidence-report-2.1",
        }
    )
    identifier = "report-" + signature
    previous = ledger.store.rows(
        "SELECT payload FROM v3_reports WHERE id=?", (identifier,)
    )
    if previous:
        return json.loads(previous[0]["payload"])
    created = now()

    def plain(value: str) -> str:
        return " ".join(str(value).splitlines())

    lines = [
        "# SIRE uploaded-evidence investigation",
        "",
        f"Report ID: {identifier}",
        f"Created UTC: {created}",
        f"Case: {case_id}",
        "Source authenticity and physical asset association remain unverified.",
        "This report does not establish a physical root cause or a maintenance limit.",
        "",
        "## User question",
        "User question: " + plain(saved["case"]["question"]),
        "",
        "## Competing hypotheses",
    ]
    for item in saved["hypotheses"]:
        lines += [
            f"### {plain(item['mechanism'])}",
            f"Stable ID: {item['id']}; status: {item['status']}; heuristic ordering score {item['ranking_score']}, not a probability.",
            "Supporting source IDs: "
            + (", ".join(item["supporting_evidence_ids"]) or "None established"),
            "Proposed conflicting source IDs: "
            + (", ".join(item["contradicting_evidence_ids"]) or "None established"),
            "Measured falsification references: "
            + (", ".join(item["falsified_by"]) or "None established"),
            "Excluded from support because physical association is unverified: "
            + (", ".join(item.get("excluded_as_unlinked", [])) or "None recorded"),
            "Missing checks: "
            + "; ".join(plain(value) for value in item["missing_tests"]),
            "Narrative review: "
            + (
                "; ".join(item["narrative_issues"])
                if item.get("narrative_issues")
                else "No obvious text fragment flagged; causal validity remains unverified."
            ),
            "",
        ]
    if not saved["hypotheses"]:
        lines.append("Insufficient evidence to propose a defensible mechanism.")
    lines += [
        "## Source summaries",
        f"Full immutable observations, every measurement row and original provenance are retained in [the JSON audit](/api/v1/reports/{identifier}/download?format=json). Previews below are explicitly bounded.",
    ]
    if saved.get("followup_error"):
        lines += [
            "Incomplete follow-up: " + plain(saved["followup_error"]["message"]),
            "Earlier completed rounds only; this is a partial investigation.",
        ]
    for source in evidence:
        record = source["evidence"]
        lines += [
            f"Source {record['id']}: {plain(source['source']['name'])}",
            f"Class {record['source_type']}; available {record['available_at']}; observed {record['observed_at'] or 'not supplied'}; unit {record['unit'] or 'not supplied'}.",
            "Locator: "
            + json.dumps(
                {
                    key: value
                    for key, value in record["pointer"].items()
                    if key != "source_rows"
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            "Observation: "
            + json.dumps(source_summary(record), ensure_ascii=False, sort_keys=True),
            "Evidence SHA256: " + record["sha256"],
            "Source SHA256: " + source["source"]["sha256"],
            "",
        ]
    lines += ["## Actual tool executions"]
    for tool in saved["tools"]:
        lines.append(
            f"- {tool['tool']} / {tool['status']}: {tool['elapsed_seconds']} seconds; provider {tool.get('provider') or 'deterministic local tool'}; model {tool.get('model') or 'not applicable'}."
        )
    lines += [
        "Stop: " + saved.get("stop_reason", "not recorded in legacy case"),
        "",
        "## Unresolved model suggestions (unverified)",
    ] + ["- " + plain(value) for value in saved["unresolved"]]
    lines += ["", "## Limitations"] + [
        "- " + plain(value) for value in saved["limitations"]
    ]
    deferred = [
        item
        for item in saved.get("hypothesis_registry", [])
        if item["selection_state"] == "deferred"
    ]
    if deferred:
        lines += ["", f"## Deferred candidates ({len(deferred)})"] + [
            "- "
            + plain(item["definition"]["mechanism"])
            + "; retained in full JSON audit; reason "
            + plain(item["selection_rationale"]["policy"])
            for item in deferred
        ]
    markdown = "\n".join(lines) + "\n"
    result = {
        "id": identifier,
        "case_id": case_id,
        "case": saved,
        "evidence": evidence,
        "markdown": markdown,
        "created_at": created,
        "human_review_status": "unreviewed",
        "source_type": "model_generated",
        "sha256": digest({"case": saved, "evidence": evidence, "markdown": markdown}),
    }
    ledger.save("reports", result, identifier)
    return result
