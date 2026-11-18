"""Conservative structured free-text intent routing, independent of uploaded instructions."""

import re
from app.prediction.policy import default_model
from app.storage.database import Store
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.orchestration.runtime import Plan


def _prediction_clauses(content: str) -> list[str]:
    """Keep affirmative prediction clauses; negation scopes coordinated verb lists."""
    clauses = re.split(r"[.!?;\n]+|\b(?:but|however)\b", content, flags=re.I)
    result = []
    for clause in clauses:
        clause = re.sub(r"^\s*without\b[^,]+,\s*", "", clause, flags=re.I)
        action = re.search(
            r"\b(?:predict|prediction|estimate|calculate|compute|rul|remaining\s+(?:useful\s+)?life)\b",
            clause,
            re.I,
        )
        if action and not re.search(
            r"\b(?:do not|must not|should not|not to|never|avoid|cannot|can't|don't|doesn't|shouldn't|mustn't|no need to)\b|"
            r"\bwithout\s+(?:predicting|estimating|calculating|computing)\b|\b(?:no|not|without)\s+(?:\w+\s+){0,2}$",
            clause[: action.start()],
            re.I,
        ):
            result.append(clause)
    return result


def rul_requested(content: str) -> bool:
    """Require an affirmative calculation request, not an exclusion or mere RUL mention."""
    return any(
        re.search(
            r"\b(?:predict|estimate|calculate|compute)\b.{0,160}\b(?:rul|remaining\s+useful\s+life)\b",
            clause,
            re.I,
        )
        for clause in _prediction_clauses(content)
    )


def nasa_command(content: str) -> dict | None:
    """Recognize explicit prediction commands only when both NASA subset and engine are named."""
    content = " ".join(_prediction_clauses(content))
    if not re.search(
        r"\b(?:predict|prediction|estimate|calculate|rul|remaining\s+(?:useful\s+)?life)\b",
        content,
        re.I,
    ):
        return None
    dataset = re.search(r"\b(FD00[1-4])\b", content, re.I)
    engine = re.search(r"\bengine\s+(\d{1,3})\b", content, re.I)
    if not dataset or not engine:
        return None
    subset = dataset.group(1).upper()
    model = default_model(subset)
    return {
        "dataset": subset,
        "asset_id": f"{subset}-ENGINE-{int(engine.group(1)):03d}",
        "model_id": model["model_id"],
    }


def investigation_requested(
    content: str, forced: bool = False, has_evidence: bool = False
) -> bool:
    """Route explicit causal requests; descriptions and negated failure mentions stay conversational."""
    if forced:
        return True
    text = content.casefold().strip()
    if re.match(
        r"(?:what is|what are|how does|how do|explain how|define|describe the concept)\b",
        text,
    ) and not re.search(r"\b(?:this|my|attached|our)\b", text):
        return False
    if re.search(
        r"\b(?:investigate|investigation|diagnose|diagnosis)\b", text
    ) and not re.search(
        r"\b(?:no|without|do not|don't)\s+(?:fault\s+)?(?:investigat|diagnos)", text
    ):
        return True
    if re.search(
        r"root cause|compare.*hypothes|why.*(?:fail|damag|break|wear|nois|vibrat|overheat)|(?:fail|damag|break).{0,50}why",
        text,
    ):
        return True
    return has_evidence and bool(
        re.search(
            r"(?:what|which).*(?:cause|explain|account)|propose.*(?:mechanism|hypothes)",
            text,
        )
    )


def saved_report_plan(
    content: str, store: Store, conversation_id: str
) -> "Plan | None":
    """Route an explicit export request to the actual latest saved evidence case."""
    if not re.search(
        r"\b(?:export|download|create|prepare|generate)\b.*\b(?:report|pdf)\b",
        content,
        re.I,
    ):
        return None
    from app.orchestration.runtime import Plan, Invocation

    rows = store.rows(
        "SELECT id FROM cases WHERE conversation_id=? ORDER BY created_at DESC LIMIT 1",
        (conversation_id,),
    )
    if not rows:
        return None
    return Plan(
        intent="evidence_report_export",
        goals=["Export the actual saved uploaded-evidence investigation"],
        tools=[
            Invocation(
                tool_id="evidence_case.report", arguments={"case_id": rows[0]["id"]}
            )
        ],
    )


def transcription_plan(
    content: str, attachments: list[dict], conversation_id: str
) -> "Plan | None":
    """Route a pure transcription request without turning its input into engineering evidence."""
    if not attachments or any(a["kind"] != "audio" for a in attachments):
        return None
    words = set(re.findall(r"\w+", content.lower()))
    allowed = {
        "please",
        "transcribe",
        "transcript",
        "transcription",
        "show",
        "give",
        "me",
        "the",
        "this",
        "these",
        "my",
        "attached",
        "uploaded",
        "file",
        "files",
        "recording",
        "recordings",
        "audio",
        "speech",
        "voice",
        "clip",
        "clips",
        "verbatim",
        "only",
        "exactly",
        "write",
        "down",
        "what",
        "does",
        "it",
        "say",
        "word",
        "for",
    }
    if (
        not words.intersection({"transcribe", "transcript", "transcription"})
        or not words <= allowed
    ):
        return None
    from app.orchestration.runtime import Plan, Invocation

    return Plan(
        intent="direct_transcription",
        goals=[
            "Return actual saved automatic transcripts as unverified input provenance"
        ],
        tools=[
            Invocation(
                tool_id="audio.transcript",
                arguments={
                    "conversation_id": conversation_id,
                    "attachment_id": a["id"],
                },
            )
            for a in attachments
        ],
    )
