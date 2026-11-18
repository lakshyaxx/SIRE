"""Additive V3 routes; existing chat and prediction contracts remain intact."""

import asyncio
import json
import uuid
from fastapi import APIRouter, Request, File, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.orchestration.runtime import Invocation, Plan, Runner
from app.orchestration.tools import build_registry
from app.simulation.repository import Observations
from app.investigation.facility import investigate_facility
from app.assets.fleet import overview
from app.knowledge.case_memory import similar_cases, annotations, annotate
from app.simulation.what_if import compare
from app.reports import engineering
from app.evidence.verification import Claim, verify_claim
from fastapi.responses import Response
from typing import Literal

router = APIRouter(prefix="/api/v1")


@router.get("/providers/registry")
def provider_registry() -> dict:
    """Expose real specialist configuration and explicit unsupported optional providers."""
    from app.providers.registry import providers

    return {"providers": [row.model_dump() for row in providers()]}


@router.get("/runtime/resources")
def runtime_resources() -> dict:
    """Observe actual resource queue and provider residency without loading any model."""
    from app.providers.registry import resources

    return resources()


class ClaimCheckRequest(BaseModel):
    """Check claims only against sources available in the selected local conversation."""

    model_config = ConfigDict(extra="forbid")
    conversation_id: str = Field(min_length=1, max_length=100)
    claims: list[Claim] = Field(min_length=1, max_length=64)


@router.post("/evidence/verify")
def check_claims(body: ClaimCheckRequest, request: Request) -> dict:
    """Return qualified deterministic source checks, never calibrated diagnosis confidence."""
    store = request.app.state.store
    store.conversation(body.conversation_id)
    attachments = store.attachments(body.conversation_id)
    owned = {row["id"] for row in attachments}
    known = {
        identifier
        for row in attachments
        for identifier in row["metadata"].get("evidence_ids", [])
    }
    for message in store.messages(body.conversation_id):
        known.update(row["id"] for row in message["metadata"].get("evidence", []))
        known.update(message["metadata"].get("workspace", {}).get("evidence_ids", []))
    ledger = Ledger(store)
    for claim in body.claims:
        for identifier in claim.source_ids:
            if identifier not in known:
                resolved = ledger.resolve(identifier)["evidence"]
                if resolved["pointer"].get("attachment_id") not in owned:
                    raise SireError(
                        "evidence_scope_mismatch",
                        "Source is not linked to this conversation.",
                        404,
                    )
    return {
        "verifications": [
            verify_claim(claim, ledger).model_dump(mode="json") for claim in body.claims
        ],
        "scope": "Exact source agreement and conservative classification; no physical-truth or calibrated confidence claim.",
    }


def observations(request: Request) -> Observations:
    """Bind only the synthetic observable database, never evaluator truth."""
    return Observations(request.app.state.store.path.parent / "scenarios")


@router.get("/scenarios")
def scenarios(request: Request) -> dict:
    """List real generated SQLite trials, explicitly labeled simulation."""
    return {
        "scenarios": observations(request).scenarios(),
        "source_type": "sire_synthetic_scenario",
    }


@router.get("/scenarios/{identifier}")
def scenario(identifier: str, request: Request) -> dict:
    """Show observable metadata, excluding hidden fault labels."""
    return observations(request).scenario(identifier)


@router.get("/scenarios/{identifier}/assets")
@router.get("/assets")
def assets(
    request: Request, identifier: str | None = None, scenario_id: str | None = None
) -> dict:
    """Require explicit scenario scope for repeated industrial asset names."""
    selected = identifier or scenario_id
    if not selected:
        raise SireError("scenario_required", "Select a scenario.")
    return {"assets": observations(request).assets(selected)}


@router.get("/assets/{asset_id}/relations")
def relations(
    asset_id: str,
    scenario_id: str,
    request: Request,
    as_of: str | None = None,
    depth: int = 1,
    direction: str = "both",
) -> dict:
    """Expose typed directed valid edges with bounded traversal."""
    return {
        "relations": observations(request).relations(
            scenario_id, asset_id, as_of, depth, direction
        )
    }


@router.get("/assets/{asset_id}/telemetry")
def facility_telemetry(
    asset_id: str,
    scenario_id: str,
    request: Request,
    as_of: str | None = None,
    start: str | None = None,
    limit: int = 1000,
    offset: int = 0,
) -> dict:
    """Return source rows behind a strict historical fence, with explicit units."""
    repo = observations(request)
    from app.simulation.settings import CONFIG

    return {
        "records": repo.telemetry(scenario_id, asset_id, as_of, start, limit, offset),
        "as_of": repo.cutoff(scenario_id, as_of),
        "source_type": "sire_synthetic_scenario",
        "analysis_limit": CONFIG["max_analysis_rows"],
    }


@router.get("/incidents/{identifier}/timeline")
def timeline(identifier: str, request: Request, as_of: str | None = None) -> dict:
    """Scenario review IDs are incident scopes; future/late notes are withheld server-side."""
    repo = observations(request)
    return {
        "events": repo.events(identifier, as_of),
        "as_of": repo.cutoff(identifier, as_of),
        "source_type": "sire_synthetic_scenario",
    }


class ExecuteRequest(BaseModel):
    """Choose an explicit, whitelisted tool without arbitrary code execution."""

    model_config = ConfigDict(extra="forbid")
    tool_id: str
    arguments: dict = Field(default_factory=dict)


@router.get("/capabilities")
def capabilities(request: Request) -> dict:
    """List actual bound adapters and installed local-provider availability."""
    from app.voice.capabilities import capabilities as voice_capability_state

    registry = build_registry(request.app.state.store)
    tools = [item[0].model_dump() for item in registry.tools.values()]
    health = request.app.state.chat.provider.health()
    for tool in tools:
        tool["health_check"] = {"status": "bound_adapter"}
        if tool["tool_id"] == "llm.chat":
            tool["availability"] = (
                "available" if health.get("text_ready") else "provider_unavailable"
            )
            tool["health_check"] = health
        if (
            tool["tool_id"]
            in {"temporal.summary", "assets.relations", "facility.investigate"}
            and not observations(request).path.is_file()
        ):
            tool["availability"] = "requires_generated_scenarios"
    return {
        "tools": tools,
        "privacy": "local_only",
        "voice": voice_capability_state(),
    }


@router.post("/intelligence/execute")
async def execute(body: ExecuteRequest, request: Request) -> dict:
    """Execute one genuine specialist call and return its persisted operational trace."""
    store = request.app.state.store
    call = Invocation(**body.model_dump())
    plan = Plan(
        intent=body.tool_id,
        goals=["Execute an explicitly requested local specialist"],
        tools=[call],
        deadline_seconds=180,
    )
    runner = Runner(Ledger(store), plan, build_registry(store))
    try:
        result = await runner.execute(call, asyncio.Event())
        runner.finish("complete")
        return {"result": result, "run_id": runner.id, "trace": runner.trace}
    except ValidationError as exc:
        runner.finish("error")
        raise SireError(
            "invalid_tool_input", "Tool arguments do not match its schema."
        ) from exc
    except Exception:
        runner.finish("error")
        raise


@router.get("/evidence/{identifier}")
def evidence(identifier: str, request: Request, as_of: str | None = None) -> dict:
    """Resolve exact source/observation identity; never fabricate absent references."""
    result = Ledger(request.app.state.store).resolve(identifier)
    if as_of:
        from app.simulation.repository import utc

        cutoff = utc(as_of)
        record = result["evidence"]
        if record["available_at"] > cutoff or (
            record["observed_at"] and record["observed_at"] > cutoff
        ):
            raise SireError(
                "evidence_not_yet_available",
                "Evidence was unavailable at this historical cutoff.",
                404,
            )
    return result


@router.get("/runs/{identifier}/trace")
def trace(identifier: str, request: Request) -> dict:
    """Read a privacy-safe operational record, not private model reasoning."""
    return Ledger(request.app.state.store).get("runs", identifier)


class FacilityRequest(BaseModel):
    """Explicit scenario/asset/time scope; no hidden truth or NASA model arguments."""

    model_config = ConfigDict(extra="forbid")
    scenario_id: str
    asset_id: str
    as_of: str | None = None
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), max_length=100)


@router.post("/facility/investigations")
async def facility_case(body: FacilityRequest, request: Request) -> dict:
    """Execute actual graph/time-series/evidence tools against the selected observed prefix."""
    return await run_facility(body, request)


async def run_facility(
    body: FacilityRequest, request: Request, parent: str | None = None
) -> dict:
    """Track cancellable jobs without touching equipment or starting unbounded workers."""
    if not hasattr(request.app.state, "facility_jobs"):
        request.app.state.facility_jobs = {}
    jobs = request.app.state.facility_jobs
    if body.request_id in jobs:
        raise SireError("investigation_busy", "Request ID is already active.", 409)
    event = asyncio.Event()
    jobs[body.request_id] = event
    try:
        return await investigate_facility(
            observations(request),
            Ledger(request.app.state.store),
            body.scenario_id,
            body.asset_id,
            body.as_of,
            event,
            parent_case_id=parent,
        )
    except asyncio.CancelledError as exc:
        raise SireError(
            "investigation_cancelled",
            "Investigation stopped; completed trace records were preserved.",
            409,
        ) from exc
    finally:
        jobs.pop(body.request_id, None)


@router.post("/facility/investigations/{identifier}/cancel")
def cancel_facility(identifier: str, request: Request) -> dict:
    """Stop downstream work of a known active facility request."""
    event = getattr(request.app.state, "facility_jobs", {}).get(identifier)
    if event:
        event.set()
    return {"cancellation_requested": event is not None}


@router.get("/cases/{identifier}")
def case_detail(identifier: str, request: Request) -> dict:
    """Reopen a preserved V3 evidence snapshot and hypothesis revision."""
    ledger = Ledger(request.app.state.store)
    return {
        **ledger.get("cases", identifier),
        "review_annotations": annotations(ledger, identifier),
    }


class ReviewInput(BaseModel):
    """Human notes remain assertions, never measured source facts."""

    note: str = Field(min_length=1, max_length=2000)
    review_status: Literal["provisional", "human_reviewed_simulation", "superseded"] = (
        "provisional"
    )


@router.post("/cases/{identifier}/annotations")
def review_case(identifier: str, body: ReviewInput, request: Request) -> dict:
    """Append a review without erasing a prior case, source, or hypothesis revision."""
    return annotate(
        Ledger(request.app.state.store), identifier, body.note, body.review_status
    )


@router.get("/cases")
def case_memory(
    request: Request, asset_id: str | None = None, as_of: str | None = None
) -> dict:
    """Retrieve simulation cases as provisional precedent, never as confirmed facts."""
    from app.simulation.repository import utc

    rows = request.app.state.store.rows(
        "SELECT payload FROM v3_cases ORDER BY created_at DESC LIMIT 100"
    )
    import json

    items = [json.loads(r["payload"]) for r in rows]
    return {
        "cases": [
            {
                "id": c["id"],
                "asset_id": c["asset_id"],
                "scenario_id": c["scenario_id"],
                "as_of": c["as_of"],
                "confirmation_status": c["confirmation_status"],
                "abstained": c["abstained"],
            }
            for c in items
            if (not asset_id or c["asset_id"] == asset_id)
            and (
                not as_of
                or (c["as_of"] <= utc(as_of) and c["created_at"] <= utc(as_of))
            )
        ]
    }


@router.post("/cases/{identifier}/continue")
async def continue_case(
    identifier: str, body: FacilityRequest, request: Request
) -> dict:
    """Create a new revision with expanded visible evidence; preserve the original snapshot."""
    ledger = Ledger(request.app.state.store)
    prior = ledger.get("cases", identifier)
    if prior["scenario_id"] != body.scenario_id or prior["asset_id"] != body.asset_id:
        raise SireError("case_scope_mismatch", "Continue the same scenario and asset.")
    return await run_facility(body, request, identifier)


@router.get("/fleet/overview")
def fleet(
    scenario_id: str,
    request: Request,
    as_of: str | None = None,
    peer_asset_id: str | None = None,
) -> dict:
    """Expose actual quality/trend indicators with no universal failure score."""
    return overview(
        observations(request),
        Ledger(request.app.state.store),
        scenario_id,
        as_of,
        peer_asset_id,
    )


@router.get("/cases/{identifier}/similar")
def similar(identifier: str, request: Request, as_of: str | None = None) -> dict:
    """Retrieve actual provisional case snapshots and explicit mechanism differences."""
    return {"cases": similar_cases(Ledger(request.app.state.store), identifier, as_of)}


class WhatIfRequest(BaseModel):
    """Bounded simulation-only intervention; real uploaded data is not accepted."""

    model_config = ConfigDict(extra="forbid")
    scenario_id: str
    as_of: str | None = None
    service_hour: int | None = Field(default=None, ge=0, le=96)
    load_factor: float | None = Field(default=None, ge=0.5, le=1.2)


@router.post("/simulations/what-if")
def what_if(body: WhatIfRequest, request: Request) -> dict:
    """Regenerate the same seed, returning trajectories and explicit changed assumptions."""
    changes = body.model_dump(exclude_none=True)
    changes.pop("scenario_id")
    changes.pop("as_of", None)
    return compare(
        observations(request),
        Ledger(request.app.state.store),
        body.scenario_id,
        changes,
        body.as_of,
    )


@router.post("/cases/{identifier}/report")
def make_report(identifier: str, request: Request) -> dict:
    """Freeze actual case and evidence snapshots for genuine downloads."""
    report = engineering.create(Ledger(request.app.state.store), identifier)
    return {
        k: report[k]
        for k in ["id", "case_id", "sha256", "human_review_status", "source_type"]
    }


@router.get("/reports/{identifier}")
def report_detail(identifier: str, request: Request) -> dict:
    """Read the reproducible report source and evidence integrity manifest."""
    return Ledger(request.app.state.store).get("reports", identifier)


@router.post("/evidence-investigations/{identifier}/report")
def make_evidence_report(identifier: str, request: Request) -> dict:
    """Export an actual general evidence case without pretending it is a simulated facility."""
    from app.reports.evidence_case import create

    value = create(Ledger(request.app.state.store), identifier)
    return {
        key: value[key]
        for key in ["id", "case_id", "sha256", "source_type", "created_at"]
    }


@router.get("/reports/{identifier}/download")
def download_report(
    identifier: str,
    request: Request,
    format: Literal["markdown", "pdf", "json"] = "markdown",
) -> Response:
    """Download real generated bytes with safe non-user-controlled filenames."""
    report = Ledger(request.app.state.store).get("reports", identifier)
    content = (
        engineering.pdf_bytes(report)
        if format == "pdf"
        else (
            json.dumps(report, ensure_ascii=False, sort_keys=True).encode()
            if format == "json"
            else report["markdown"].encode()
        )
    )
    return Response(
        content,
        media_type=(
            "application/pdf"
            if format == "pdf"
            else (
                "application/json"
                if format == "json"
                else "text/markdown; charset=utf-8"
            )
        ),
        headers={
            "Content-Disposition": f'attachment; filename="sire-{report["sha256"][:12]}.{format if format in {"pdf","json"} else "md"}"',
            "X-Report-Integrity": report["sha256"],
        },
    )


@router.post("/evidence/upload")
async def upload_evidence(request: Request, file: UploadFile = File(...)) -> dict:
    """Validate and snapshot uploaded sources privately, with resolvable row/paragraph pointers."""
    from app.evidence.intake import ingest
    from app.core.config import SETTINGS

    return await asyncio.to_thread(
        ingest,
        Ledger(request.app.state.store),
        file.filename or "upload",
        await file.read(SETTINGS["max_upload_bytes"] + 1),
    )


@router.get("/voice/capabilities")
def voice_capabilities() -> dict:
    """Expose installed local capability limits; never silently use hosted recognition."""
    from app.voice.capabilities import capabilities

    return capabilities()


@router.post("/voice/transcribe")
async def transcribe(
    file: UploadFile = File(...), profile: Literal["asr", "asr_base"] | None = None
) -> dict:
    """Transcribe actual bounded PCM with the configured local worker."""
    from app.voice.service import transcribe_bytes, validate_audio
    from pathlib import Path

    content = await file.read(10000001)
    if len(content) > 10000000:
        raise SireError("audio_too_large", "Audio exceeds the upload limit.", 413)
    suffix = Path(file.filename or "recording.wav").suffix.lower()
    validate_audio(content, suffix)
    from app.media.runtime import model_files, POLICY, DEPENDENCIES

    selected_profile = profile or POLICY.get("asr_default_profile", "asr")
    model_files(selected_profile, verify=False)
    if not (DEPENDENCIES / "sherpa_onnx").is_dir():
        raise SireError(
            "asr_unavailable",
            "No configured local ASR runtime/model; type the question or run scripts/setup_media.py.",
            503,
        )
    return await asyncio.to_thread(
        transcribe_bytes, content, None, suffix, None, profile
    )


class SpeechRequest(BaseModel):
    """Bounded local synthesis or cancellation request."""

    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1200)
    request_id: str | None = Field(default=None, max_length=100)


class MediaCancel(BaseModel):
    """Opaque active media job identity."""

    request_id: str = Field(min_length=1, max_length=100)


@router.post("/voice/speak")
async def speak(body: SpeechRequest) -> Response:
    """Return genuine locally generated WAV, never browser cloud speech."""
    from app.media.runtime import run

    output = await asyncio.to_thread(run, "tts", {"text": body.text}, body.request_id)
    return Response(
        output["audio_bytes"],
        media_type="audio/wav",
        headers={
            "X-Speech-Model": output["model"],
            "X-Audio-Frames": str(output["frames"]),
            "X-Speech-Warnings": str(len(output["warnings"])),
            "X-Speech-Cache": "hit" if output.get("cache", {}).get("hit") else "miss",
            "X-Speech-Elapsed": str(output.get("elapsed_seconds", "")),
            "X-Speech-Phase-Timings": json.dumps(output.get("phase_timings", {})),
        },
    )


@router.post("/voice/cancel")
def cancel_voice(body: MediaCancel) -> dict:
    """Stop an active worker and release its local model budget."""
    from app.media.runtime import cancel

    return {"cancellation_requested": cancel(body.request_id)}
