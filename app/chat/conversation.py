"""Transport-independent conversation routing and documented application capabilities."""

import hashlib
import re
from pathlib import Path
import yaml
from app.core.config import ROOT
from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.investigation.schemas import EvidenceItem
from app.storage.database import Store

POLICY = yaml.safe_load((ROOT / "config/conversation.yaml").read_text(encoding="utf-8"))
MANIFEST = ROOT / "config/capabilities.yaml"


def fast_route(question: str, history: list[dict] | None = None) -> str | None:
    """Recognize complete social requests or application self-description, not attached evidence."""
    text = question.strip()
    if not engineering_question(text) and re.fullmatch(
        POLICY["social_pattern"], text, re.I
    ):
        return "social"
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    previous = next(
        (
            row
            for row in reversed(history or [])
            if row["role"] == "assistant" and row["status"] == "complete"
        ),
        None,
    )
    previous_topic = (previous or {}).get("metadata", {}).get("response_topic")
    if previous_topic not in {*manifest.get("topic_aliases", {}), "overview", "limits"}:
        previous_topic = None
    case_scope = re.search(
        r"\b[A-Za-z][A-Za-z0-9_]*-\d[\w-]*\b|\b(?:investigate|diagnose)\b", text, re.I
    )
    definition = re.search(
        r"\b(?:what|how|explain|describe|mean|example|simply|simpler)\b", text, re.I
    )
    scoped = previous_topic or re.search(
        r"\b(?:sire|this project|the project|your|you|its)\b", text, re.I
    )
    if not case_scope and definition:
        for topic, aliases in manifest.get("topic_aliases", {}).items():
            if any(
                re.search(r"\b" + re.escape(alias) + r"\b", text, re.I)
                for alias in aliases
            ):
                if scoped or topic in {"hypotheses", "orchestrator"}:
                    return topic
        if scoped and re.search(
            r"\b(?:limitations?|cannot|can.t|uncertain)\b", text, re.I
        ):
            return "limits"
    if (
        previous_topic
        and not case_scope
        and re.fullmatch(
            r"(?:in (?:this|the) project|(?:please )?(?:explain|describe)(?: it| that| this)?(?: simply| in simple terms)?|(?:how|why) does (?:it|that) work|what does (?:it|that) mean|(?:give|show) me an example)[.!?\s]*",
            text,
            re.I,
        )
    ):
        return previous_topic
    if re.search(r"\b(?:your|sire(?:'s)?)\s+hypothes(?:is|es)\s+engine\b", text, re.I):
        if re.search(r"\b(?:how|what|explain|describe)\b", text, re.I):
            return "hypotheses"
    if (
        not engineering_question(text)
        and re.search(r"\bsire\b", text, re.I)
        and re.search(
            r"\b(?:what|explain|describe|about|capabilit|stand)\w*\b", text, re.I
        )
    ):
        return "overview"
    if re.fullmatch(r"(?:what can you do|tell me about yourself)[.!?\s]*", text, re.I):
        return "overview"
    return None


def engineering_question(question: str) -> bool:
    """Keep source/claim validation for engineering claims, regardless of input transport."""
    return bool(re.search(POLICY["engineering_pattern"], question, re.I))


def source_followup(question: str) -> bool:
    """Only consult previous source context when the current request refers to it."""
    if re.search(POLICY["without_sources_pattern"], question, re.I) and not re.search(
        POLICY["explicit_source_reference_pattern"], question, re.I
    ):
        return False
    return bool(re.search(POLICY["source_followup_pattern"], question, re.I))


def input_audio(
    store: Store,
    cid: str,
    selected: list[dict],
    question: str,
    identifier: str | None,
    voice: bool,
) -> tuple[list[dict], dict | None]:
    """Separate explicitly submitted speech input from externally analyzed audio evidence."""
    if identifier is None and voice and len(selected) == 1:
        item = selected[0]
        if (
            item["kind"] == "audio"
            and item["metadata"].get("transcript", {}).get("text", "").strip()
            == question.strip()
        ):
            identifier = item["id"]
    if identifier is None:
        return selected, None
    item = store.attachment(identifier, cid)
    transcript = item["metadata"].get("transcript")
    if item["kind"] != "audio" or not transcript:
        raise SireError(
            "invalid_input_audio",
            "Speech input must reference an actual transcribed audio attachment in this conversation.",
            422,
        )
    return [row for row in selected if row["id"] != identifier], {
        "kind": "speech_input",
        "attachment_id": identifier,
        "sha256": item["sha256"],
        "transcript_model": transcript["model"],
        "transcript_provider": transcript["provider"],
        "transcript_unverified": True,
        "edited": transcript["text"].strip() != question.strip(),
        "scope": "Input provenance; not independent evidence for the answer",
    }


def history_turns(history: list[dict], external: bool = False) -> list[dict]:
    """Use completed user/assistant pairs; failed, cancelled and unpaired turns cannot poison prompts."""
    turns: list[dict] = []
    user = None
    for row in history:
        if row["role"] == "user":
            user = row
        elif row["role"] == "assistant" and user is not None:
            evidence = row["metadata"].get("evidence", [])
            substantive = any(
                item.get("modality") not in {"audio", "application_documentation"}
                for item in evidence
            )
            if (
                row["status"] == "complete"
                and not row["metadata"].get("error")
                and (external or not substantive)
            ):
                for item in (user, row):
                    text = re.sub(
                        r"\[(?:E\d+|(?:EV|SRC):[^\]]+|[a-f\d]{24,32}(?::[^\]]+)?)\]",
                        "",
                        item["content"],
                        flags=re.I,
                    )
                    turns.append({"role": item["role"], "content": text})
            user = None
    turns = turns[-POLICY["history_turns"] :]
    while (
        turns
        and sum(len(row["content"]) for row in turns) > POLICY["history_characters"]
    ):
        turns = turns[2:]
    return turns


def describe(store: Store, topic: str, question: str = "") -> tuple[str, EvidenceItem]:
    """Return exact authored capability-manifest text with a real resolvable source snapshot."""
    raw = MANIFEST.read_bytes()
    data = yaml.safe_load(raw)
    variant = (
        "examples"
        if re.search(r"\bexample\b", question, re.I)
        else (
            "plain"
            if re.search(r"\b(?:simple|simply|simpler|brief|short)\b", question, re.I)
            else ""
        )
    )
    text = data.get(variant, {}).get(topic, data[topic])
    if topic != "limits" and data.get("topic_limits", {}).get(topic):
        text += "\n\n" + data["topic_limits"][topic]
    record = Ledger(store).add(
        "manually_entered",
        "SIRE application capability manifest",
        {
            "text": text,
            "spoken_text": data["spoken"][topic],
            "version": data["version"],
            "topic": topic,
        },
        {"path": Path(MANIFEST).relative_to(ROOT).as_posix(), "topic": topic},
        method="exact_application_capability_manifest",
        quality="software_documentation",
        content_sha256=hashlib.sha256(raw).hexdigest(),
    )
    item = EvidenceItem(
        id=record.id,
        modality="application_documentation",
        kind="document_guidance",
        source_id=record.source_id,
        observation=text,
        locator=f"config/capabilities.yaml / {topic}",
        reliability="medium",
        limitations=[
            "Authored software capability documentation, not physical evidence or a live provider readiness probe."
        ],
    )
    return text + f"\n\nSource: [{record.id}]", item


def speech_summary(topic: str) -> str:
    """Read the exact authored concise speech variant from the same capability source."""
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["spoken"][topic]
