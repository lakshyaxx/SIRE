"""Additive specialist contracts and dispatch through SIRE's existing runner."""

import asyncio
from contextlib import suppress
import time
import logging
import hashlib
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import Field, ValidationError
from app.core.config import SETTINGS
from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.orchestration.runtime import Invocation, Plan, Runner
from app.orchestration.tools import build_registry
from app.providers.specialists import SpeechInput
from app.providers.contracts import (
    SpecialistCancel,
    SpecialistRequest,
    SpecialistResponse,
)

router = APIRouter(prefix="/api/v1/specialists", tags=["specialists"])
LOGGER = logging.getLogger(__name__)


class SpeechStreamRequest(SpeechInput):
    """Actual sentence WAV delivery; no continuous voice-call or partial-token claim."""

    conversation_id: str = Field(min_length=1, max_length=100)
    request_id: str = Field(min_length=1, max_length=100)


@router.post("/speech/stream")
async def speech_stream(
    body: SpeechStreamRequest, request: Request
) -> StreamingResponse:
    """Emit each real completed WAV as it becomes usable, preserving cancellation/traces."""
    from app.media.runtime import POLICY
    from app.voice.chunks import split_text
    import json

    store = request.app.state.store
    store.conversation(body.conversation_id)
    chunks = split_text(
        body.text, POLICY["tts_chunk_characters"], POLICY["max_tts_chunks"]
    )
    key = (body.conversation_id, body.request_id)
    calls = request.app.state.specialist_calls
    if key in calls:
        raise SireError(
            "specialist_request_active", "This request is already active.", 409
        )
    event = asyncio.Event()
    invocations = [
        Invocation(
            tool_id="speech.synthesize",
            arguments={"text": text, "voice_id": body.voice_id, "speed": body.speed},
        )
        for text in chunks
    ]
    runner = Runner(
        Ledger(store),
        Plan(
            intent="sentence_speech_delivery",
            goals=["Deliver only actual generated audio segments"],
            tools=invocations,
            deadline_seconds=SETTINGS.get("chat_budget_seconds", 300),
        ),
        build_registry(store, request.app.state.chat.provider, event),
    )
    calls[key] = event

    async def events():
        began = time.perf_counter()
        status = "complete"
        delivered = 0

        def encode(value):
            return "data: " + json.dumps(value) + "\n\n"

        try:
            yield encode(
                {
                    "type": "started",
                    "run_id": runner.id,
                    "request_id": body.request_id,
                    "segments": len(chunks),
                    "streaming_mode": "completed_sentence_wav_segments",
                }
            )
            for index, invocation in enumerate(invocations):
                value = await runner.execute(invocation, event)
                if value.get("cache_hit"):
                    value = {
                        **value,
                        "audio": {
                            **value["audio"],
                            "cache": {
                                "hit": True,
                                "scope": "Reused the exact successful generated WAV within this run",
                            },
                        },
                    }
                delivered += 1
                yield encode(
                    {
                        "type": "audio_chunk",
                        "index": index,
                        "audio": value["audio"],
                        "elapsed_seconds": time.perf_counter() - began,
                    }
                )
        except asyncio.CancelledError:
            status = "cancelled"
        except GeneratorExit:
            status = "cancelled"
            raise
        except SireError as exc:
            status = "error"
            yield encode({"type": "error", "code": exc.code, "message": exc.message})
        except Exception as exc:
            LOGGER.error("Speech stream failed type=%s", type(exc).__name__)
            status = "error"
            yield encode(
                {
                    "type": "error",
                    "code": "speech_stream_failed",
                    "message": "Speech segment failed; no audio substituted.",
                }
            )
        finally:
            event.set()
            calls.pop(key, None)
            runner.finish(status)
        yield encode(
            {
                "type": "done",
                "status": status,
                "run_id": runner.id,
                "delivered_segments": delivered,
                "elapsed_seconds": time.perf_counter() - began,
            }
        )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/retrieval/rebuild")
def clear_retrieval(body: SpecialistCancel, request: Request) -> dict:
    """Clear only the case's derived embeddings; sources and protected models stay intact."""
    from app.knowledge.semantic import clear

    return {
        "deleted_derived_vectors": clear(request.app.state.store, body.conversation_id),
        "next_search": "Rebuilds from exact current source chunks using pinned model version",
    }


@router.get("/contracts")
def contracts(request: Request) -> dict:
    """Return actual registered input/output schemas, never speculative provider contracts."""
    registry = build_registry(request.app.state.store)
    return {
        "contract_version": "1.0",
        "state_namespace": hashlib.sha256(
            str(request.app.state.store.path.resolve()).encode()
        ).hexdigest(),
        "tools": [spec.model_dump() for spec, _, _ in registry.tools.values()],
        "scheduler": "app.providers.resources.SCHEDULER",
        "source_policy": "Model interpretations are unverified; speech transcripts are input provenance.",
    }


@router.post("/cancel")
def cancel(body: SpecialistCancel, request: Request) -> dict:
    """Signal only a currently active call belonging to this conversation."""
    event = request.app.state.specialist_calls.get(
        (body.conversation_id, body.request_id)
    )
    if event:
        event.set()
    return {"cancellation_requested": event is not None}


@router.post("/execute", response_model=SpecialistResponse)
async def execute(
    body: SpecialistRequest, request: Request
) -> SpecialistResponse | JSONResponse:
    """Validate, execute, cancel and trace a real tool without a parallel model scheduler."""
    store = request.app.state.store
    store.conversation(body.conversation_id)
    key = (body.conversation_id, body.request_id)
    calls = request.app.state.specialist_calls
    if key in calls:
        raise SireError(
            "specialist_request_active", "This request is already active.", 409
        )
    event = asyncio.Event()
    registry = build_registry(store, request.app.state.chat.provider, event)
    if body.tool_id not in registry.tools:
        raise SireError(
            "specialist_unavailable", "This specialist is not registered.", 503
        )
    arguments = dict(body.arguments)
    schema = registry.tools[body.tool_id][1]
    if "conversation_id" in schema.model_fields:
        if (
            arguments.get("conversation_id", body.conversation_id)
            != body.conversation_id
        ):
            raise SireError(
                "evidence_scope_mismatch", "Conversation scopes differ.", 404
            )
        arguments["conversation_id"] = body.conversation_id
    invocation = Invocation(tool_id=body.tool_id, arguments=arguments)
    runner = Runner(
        Ledger(store),
        Plan(
            intent="specialist_execution",
            goals=["Execute the requested local capability with typed provenance"],
            tools=[invocation],
            deadline_seconds=SETTINGS.get("chat_budget_seconds", 300),
        ),
        registry,
    )
    calls[key] = event
    began = time.perf_counter()

    async def disconnect() -> None:
        while not event.is_set():
            if await request.is_disconnected():
                event.set()
                return
            await asyncio.sleep(0.1)

    watcher = asyncio.create_task(disconnect())
    output = None
    error = None
    status, status_code = "complete", 200
    try:
        output = await runner.execute(invocation, event)
        for identifier in output.get("evidence_ids", []):
            runner.ledger.resolve(identifier)
    except asyncio.CancelledError:
        event.set()
        status = "cancelled"
    except (SireError, ValidationError) as exc:
        output = None
        status = "error"
        status_code = getattr(exc, "status", 422)
        error = {
            "code": getattr(exc, "code", "specialist_validation"),
            "message": getattr(
                exc, "message", "Specialist input or output failed validation."
            ),
        }
    except Exception as exc:
        LOGGER.error("Specialist execution failed type=%s", type(exc).__name__)
        output = None
        status, status_code = "error", 500
        error = {
            "code": "specialist_failed",
            "message": "Local specialist failed; no substitute result.",
        }
    finally:
        event.set()
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher
        calls.pop(key, None)
        runner.finish(status)
    role = (
        "input_provenance"
        if body.tool_id == "audio.transcript"
        else (
            "generated_audio" if body.tool_id == "speech.synthesize" else "observations"
        )
    )
    result = SpecialistResponse(
        request_id=body.request_id,
        run_id=runner.id,
        tool_id=body.tool_id,
        status=status,
        elapsed_seconds=time.perf_counter() - began,
        output_role=role,
        output=output,
        evidence_ids=(
            output.get("evidence_ids", []) if output and role == "observations" else []
        ),
        error=error,
        provenance=[
            s["model_provenance"]
            for s in runner.trace["steps"]
            if s.get("model_provenance")
        ],
        limitations=["Source identity is not proof of physical or causal correctness."],
    )
    return (
        JSONResponse(status_code=status_code, content=result.model_dump())
        if status_code != 200
        else result
    )
