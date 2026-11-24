"""Recall persisted case state without repeating vision, prediction or proposal inference."""

import re
import json
from app.storage.database import Store


def recall_requested(question: str) -> bool:
    """Recognize follow-ups about existing decisions, preserving explicit revision requests."""
    if re.search(
        r"\b(?:revise|revisit|update|reconsider|new evidence|rerun|re-run|fresh analysis|reanaly[sz]e|(?:investigate|analy[sz]e).{0,12}again)\b",
        question,
        re.I,
    ):
        return False
    return bool(
        re.search(
            r"\b(?:why.{0,30}(?:rule out|ruled out|reject(?:ed|ions?)?|rank(?:ed|ing|ings)?|hypothes(?:is|es))|"
            r"(?:show|explain|compare|list).{0,30}(?:existing|saved|previous|those|these).{0,20}(?:hypothes(?:is|es)|findings?|candidates?)|"
            r"what.{0,20}(?:already|so far).{0,20}(?:find|found|discover(?:ed)?|learn(?:ed)?)|"
            r"what.{0,40}(?:found|discovered|learned|know).{0,15}(?:so far|already)|"
            r"check.{0,20}(?:readings|measurements|evidence).{0,10}again)\b",
            question,
            re.I,
        )
    )


def recall(
    store: Store, conversation_id: str, asset_id: str | None = None
) -> dict | None:
    """Return only this conversation's latest actual saved evidence case and typed limits."""
    store.conversation(conversation_id)
    rows = store.rows(
        "SELECT id FROM cases WHERE conversation_id=? ORDER BY created_at DESC,rowid DESC",
        (conversation_id,),
    )
    from app.orchestration.understanding import target_asset
    from app.investigation.schemas import EvidenceItem

    for row in rows:
        saved = store.result("cases", row["id"])
        case = saved["case"]
        # Repair presentation context in memory only; never rewrite an old case.
        if not case.get("asset_id"):
            case["asset_id"] = target_asset(
                case.get("question", ""),
                [
                    EvidenceItem.model_validate(item)
                    for item in case.get("evidence", [])
                ],
            )
            if case["asset_id"]:
                case["asset_identity_source"] = "user_question"
        if asset_id and (case.get("asset_id") or "").casefold() != asset_id.casefold():
            continue
        return {
            "case_id": row["id"],
            "case": saved,
            "evidence_ids": [item["id"] for item in case["evidence"]],
        }
    return None


def render(value: dict | None) -> str:
    """Explain recorded decisions without implying a tentative candidate was ruled out."""
    if value is None:
        return "No completed investigation is saved in this conversation. No hypothesis has been recorded as ruled out. Add evidence or check the status of the current background investigation."
    if value.get("attempt"):
        attempt = value["attempt"]
        return (
            f"An investigation for {attempt['asset_id'] or 'the supplied equipment'} was submitted and ended with status **{attempt['status']}**. Its original user report is retained, but no accepted case findings were saved. "
            + (
                (attempt.get("error") or {}).get("message")
                or "Review the actual execution trace before resubmitting."
            )
        )
    lines = [
        "## Saved investigation — model proposals remain unverified",
        f"Case: `{value['case_id']}`. These are recorded results; no model or measurement was rerun.",
    ]
    from app.investigation.narrative import issues

    for candidate in value["case"]["hypotheses"]:
        review = list(
            dict.fromkeys(
                [
                    *candidate.get("narrative_issues", []),
                    *issues(candidate["mechanism"]),
                ]
            )
        )
        lines += [
            f"### {candidate['mechanism']}",
            f"Recorded status: **{candidate['status']}**; evidence support: {candidate['evidence_support']}.",
            "Explanation quality: "
            + (
                "incomplete_text"
                if review
                else candidate.get("quality_status", "legacy_text_not_reassessed")
            )
            + ". Causal interpretation remains unverified.",
        ]
        if review:
            lines.append("Narrative review: " + "; ".join(review))
        for label, key in [
            ("Proposed supporting sources", "supporting_evidence_ids"),
            ("Proposed conflicting sources", "contradicting_evidence_ids"),
            ("Recorded measured falsification", "falsified_by"),
            ("Excluded as unlinked", "excluded_as_unlinked"),
        ]:
            lines.append(
                label
                + ": "
                + (
                    ", ".join(f"[{item}]" for item in candidate.get(key, []))
                    or "None recorded"
                )
            )
        lines.append(
            "Suggested checks (unverified): " + "; ".join(candidate["missing_tests"])
        )
    if not value["case"]["hypotheses"]:
        lines.append("No defensible mechanism was saved; root cause remains unknown.")
    lines.append(
        "A tentative or weakened candidate was not physically ruled out. Source identity and heuristic ranking are not causal confirmation. Explicitly request revision to run new analysis."
    )
    return "\n\n".join(lines)


def last_attempt(
    store: Store, conversation_id: str, asset_id: str | None = None
) -> dict | None:
    """Recover actual failed-request provenance without pretending a completed case was saved."""
    from app.orchestration.understanding import target_asset

    messages = store.messages(conversation_id)
    by_id = {row["id"]: row for row in messages}
    has_jobs = store.rows(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='v45_jobs'"
    )
    jobs = (
        [
            json.loads(row["payload"])
            for row in store.rows(
                "SELECT payload FROM v45_jobs WHERE conversation_id=? ORDER BY rowid DESC LIMIT 20",
                (conversation_id,),
            )
        ]
        if has_jobs
        else []
    )
    for assistant in reversed(messages):
        metadata = assistant.get("metadata", {})
        if (
            assistant["role"] != "assistant"
            or metadata.get("orchestration", {}).get("intent")
            != "incident_investigation"
        ):
            continue
        user = next(
            (
                row
                for row in messages
                if row["role"] == "user"
                and row.get("metadata", {}).get("request_id")
                and row["metadata"]["request_id"] == metadata.get("request_id")
            ),
            None,
        )
        job = next(
            (
                row
                for row in jobs
                if row.get("run_id") == metadata.get("orchestration", {}).get("run_id")
            ),
            None,
        )
        if user is None and job:
            identifier = next(
                (
                    event.get("user_message_id")
                    for event in job["events"]
                    if event.get("type") == "started"
                ),
                None,
            )
            user = by_id.get(identifier)
        if user is None:
            continue
        identity = target_asset(user["content"], [])
        if asset_id and (identity or "").casefold() != asset_id.casefold():
            continue
        return {
            "id": job["id"] if job else metadata["orchestration"]["run_id"],
            "asset_id": identity,
            "status": assistant["status"],
            "question": user["content"],
            "error": metadata.get("error"),
            "source": {
                "id": "user:" + user["id"],
                "source_id": user["id"],
                "kind": "user_claim",
                "modality": "text",
                "observation": user["content"],
                "reliability": "low",
            },
        }
    return None


def status_requested(question: str) -> bool:
    """Recognize questions about execution state rather than inventing interim findings."""
    return bool(
        re.search(
            r"\b(?:progress|what(?:'s| is) happening|what are you doing(?: right now)?|(?:job|investigation) status|status of (?:the )?(?:job|investigation)|is (?:the )?investigation (?:done|finished)|are you still (?:working|investigating))\b",
            question,
            re.I,
        )
    )


def job_status(store: Store, conversation_id: str, include_facts: bool = True) -> dict:
    """Read only this conversation's persisted job events and explicitly verified source facts."""
    store.conversation(conversation_id)
    table = store.rows(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='v45_jobs'"
    )
    rows = (
        store.rows(
            "SELECT payload FROM v45_jobs WHERE conversation_id=? ORDER BY rowid DESC LIMIT 1",
            (conversation_id,),
        )
        if table
        else []
    )
    if not rows:
        return {
            "job": None,
            "text": "No background investigation is saved in this conversation.",
            "evidence_ids": [],
        }
    job = json.loads(rows[0]["payload"])
    tools = [event for event in job["events"] if event["type"] == "tool"]
    last = tools[-1] if tools else None
    text = f"Saved investigation status: **{job['status']}**."
    if last:
        text += f" Most recent actual tool event: {last['tool']} / {last['status']}."
    text += " This is execution state, not an early diagnostic conclusion."
    evidence = []
    if include_facts:
        for event in job["events"]:
            if (
                event["type"] == "delta"
                and event.get("source")
                == "validated_descriptive_measurement_statistics"
            ):
                text += "\n\n" + event["text"]
            if event["type"] == "evidence":
                evidence = event["evidence"]
    return {
        "job_id": job["id"],
        "status": job["status"],
        "text": text,
        "evidence": evidence,
        "evidence_ids": [item["id"] for item in evidence],
    }
