"""Opt-in scoped PCM voice sessions with real VAD, durable utterances and final Whisper transcripts."""

import asyncio
import anyio
import base64
import hashlib
import io
import logging
import json
import threading
import time
import uuid
import wave
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict
from typing import Literal
from app.core.config import SETTINGS
from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.knowledge.ingestion import ingest
from app.media.runtime import model_files
from app.storage.database import now
from app.voice.vad import POLICY
from app.voice.vad_process import VadProcess

router = APIRouter(prefix="/api/v1/voice")
LOGGER = logging.getLogger(__name__)


class VoiceControl(BaseModel):
    """Only explicit voice transport controls are accepted; data is never executable."""

    model_config = ConfigDict(extra="forbid")
    op: Literal["flush", "reset", "close", "client_event"]
    event: (
        Literal[
            "playback_blocked",
            "playback_resumed",
            "explicit_interrupt",
            "transcript_suppressed",
            "speech_candidate",
        ]
        | None
    ) = None


@router.get("/session-schema")
def session_schema() -> dict:
    """Describe a real final-transcript transport without pretending Whisper streams partial words."""
    return {
        "control_schema": VoiceControl.model_json_schema(),
        "audio": {
            "encoding": "PCM16 little-endian mono",
            "sample_rate": POLICY["sample_rate"],
            "max_message_bytes": POLICY["max_pcm_message_bytes"],
        },
        "transcription": "Final VAD utterances only; configured Whisper is offline, no partial transcript claim",
        "events": [
            "ready",
            "speech_started",
            "transcribing",
            "transcript",
            "error",
            "closed",
        ],
        "max_session_seconds": POLICY["max_session_seconds"],
        "playback_guard_ms": POLICY["playback_guard_ms"],
        "interruption": "Speech onset is a candidate only. Microphone input is suppressed during playback; use Interrupt and speak for deliberate interruption.",
    }


@router.websocket("/session")
async def voice_session(websocket: WebSocket, conversation_id: str) -> None:
    """Receive user-authorized audio, isolate it to one conversation and cancel owned work on close."""
    origin = websocket.headers.get("origin")
    allowed = set(SETTINGS["cors_origins"]) | {
        f"http://{websocket.url.netloc}",
        f"https://{websocket.url.netloc}",
    }
    if origin not in allowed:
        await websocket.close(code=1008)
        return
    store = websocket.app.state.store
    active = websocket.app.state.voice_sessions
    try:
        store.conversation(conversation_id)
        model_files("vad")
    except SireError:
        await websocket.close(code=1008)
        return
    if conversation_id in active or len(active) >= POLICY["max_sessions"]:
        await websocket.close(code=1013)
        return
    active.add(conversation_id)
    try:
        await websocket.accept()
        identifier = uuid.uuid4().hex
        created = now()
        detector = VadProcess()
        queue: asyncio.Queue = asyncio.Queue(maxsize=POLICY["turn_queue"])
        send_lock = asyncio.Lock()
        current: dict = {}
        closing = asyncio.Event()
        metadata: dict = {
            "turns": [],
            "samples_received": 0,
            "format": "PCM16 mono16kHz",
            "physical_microphone": "not verifiable by server",
            "transcript_review": "Automatic transcripts remain unverified",
            "client_events": [],
        }
        status = "starting"
        digest = hashlib.sha256()
        with store.connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS v45_voice_sessions(id TEXT PRIMARY KEY,conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,created_at TEXT,updated_at TEXT,status TEXT,metadata TEXT)"
            )
            db.execute(
                "INSERT INTO v45_voice_sessions VALUES(?,?,?,?,?,?)",
                (
                    identifier,
                    conversation_id,
                    created,
                    created,
                    status,
                    json.dumps(metadata),
                ),
            )

        def save() -> None:
            with store.connection() as db:
                db.execute(
                    "UPDATE v45_voice_sessions SET updated_at=?,status=?,metadata=? WHERE id=?",
                    (now(), status, json.dumps(metadata), identifier),
                )

        async def send(event: dict) -> None:
            async with send_lock:
                await websocket.send_json({"session_id": identifier, **event})

        async def transcribe() -> None:
            while not closing.is_set():
                segment = await queue.get()
                cancellation = threading.Event()
                current["cancel"] = cancellation
                turn_id = uuid.uuid4().hex
                began = time.monotonic()
                try:
                    await send(
                        {
                            "type": "transcribing",
                            "turn_id": turn_id,
                            "start_sample": segment["start_sample"],
                            "end_sample": segment["end_sample"],
                        }
                    )
                    raw = base64.b64decode(segment["pcm_base64"], validate=True)
                    output = io.BytesIO()
                    with wave.open(output, "wb") as recording:
                        recording.setnchannels(1)
                        recording.setsampwidth(2)
                        recording.setframerate(POLICY["sample_rate"])
                        recording.writeframes(raw)
                    receipt = await asyncio.to_thread(
                        ingest,
                        store,
                        conversation_id,
                        f"voice-{identifier}-{turn_id}.wav",
                        output.getvalue(),
                        media_request_id=turn_id,
                        cancel_event=cancellation,
                    )
                    transcript = receipt["metadata"].get("transcript")
                    if not transcript:
                        error = receipt["metadata"].get("media_error", {})
                        raise SireError(
                            error.get("code", "transcription_failed"),
                            error.get("message", "No actual transcript was produced."),
                            503,
                        )
                    if not any(character.isalnum() for character in transcript["text"]):
                        raise SireError(
                            "empty_speech_transcript",
                            "No usable speech words were recognized. The recording is retained; try again or type the question.",
                            422,
                        )
                    vad = Ledger(store).add(
                        "model_generated",
                        "Voice utterance boundary",
                        {
                            key: value
                            for key, value in segment.items()
                            if key != "pcm_base64"
                        },
                        {
                            "attachment_id": receipt["id"],
                            "voice_session_id": identifier,
                        },
                        content_sha256=receipt["sha256"],
                        method="silero_vad_threshold_received_sample_clock",
                        quality="automatic_boundary_unverified",
                    )
                    elapsed = time.monotonic() - began
                    metadata["turns"].append(
                        {
                            "turn_id": turn_id,
                            "attachment_id": receipt["id"],
                            "vad_evidence_id": vad.id,
                            "elapsed_seconds": elapsed,
                        }
                    )
                    save()
                    await send(
                        {
                            "type": "transcript",
                            "turn_id": turn_id,
                            "attachment_id": receipt["id"],
                            "vad_evidence_id": vad.id,
                            "text": transcript["text"],
                            "model": transcript["model"],
                            "provider": transcript["provider"],
                            "limits": transcript["limitations"],
                            "elapsed_seconds": elapsed,
                        }
                    )
                except SireError as exc:
                    if closing.is_set():
                        continue
                    await send(
                        {
                            "type": "error",
                            "code": exc.code,
                            "message": exc.message,
                            "turn_id": turn_id,
                        }
                    )
                except Exception as exc:
                    LOGGER.error("Voice turn failed type=%s", type(exc).__name__)
                    await send(
                        {
                            "type": "error",
                            "code": "voice_turn_failed",
                            "message": "The voice turn failed; no transcript was substituted.",
                            "turn_id": turn_id,
                        }
                    )
                finally:
                    current.clear()
                    queue.task_done()

        task = asyncio.create_task(transcribe())
        started = time.monotonic()
        try:
            ready = await detector.start()
            status = "listening"
            save()
            await send(
                {
                    "type": "ready",
                    "sample_rate": ready["sample_rate"],
                    "vad_model": ready["model"],
                    "asr": "Final offline Whisper utterances, not partial words",
                }
            )
            while True:
                remaining = POLICY["max_session_seconds"] - (time.monotonic() - started)
                if remaining <= 0:
                    raise SireError(
                        "voice_session_budget",
                        "Voice session reached its time limit; start another session.",
                        409,
                    )
                message = await asyncio.wait_for(websocket.receive(), remaining)
                if message["type"] == "websocket.disconnect":
                    status = "disconnected"
                    break
                if message.get("bytes") is not None:
                    raw = message["bytes"]
                    if len(raw) % 2 or len(raw) > POLICY["max_pcm_message_bytes"]:
                        raise SireError(
                            "invalid_voice_frame",
                            "Use bounded PCM16 mono16kHz messages.",
                            422,
                        )
                    metadata["samples_received"] += len(raw) // 2
                    if (
                        metadata["samples_received"]
                        > POLICY["sample_rate"] * POLICY["max_session_seconds"]
                    ):
                        raise SireError(
                            "voice_session_budget",
                            "Voice input exceeded its bounded sample budget.",
                            413,
                        )
                    digest.update(raw)
                    result = await detector.call(
                        {
                            "op": "feed",
                            "pcm_base64": base64.b64encode(raw).decode("ascii"),
                        }
                    )
                else:
                    control = VoiceControl.model_validate_json(message.get("text", ""))
                    if control.op == "client_event":
                        if control.event is None:
                            raise ValueError("Client event name required")
                        metadata["client_events"].append(
                            {
                                "event": control.event,
                                "received_at": now(),
                                "received_sample": metadata["samples_received"],
                                "scope": "Client-reported control event; not physical microphone verification",
                            }
                        )
                        metadata["client_events"] = metadata["client_events"][-128:]
                        save()
                        continue
                    if control.op == "close":
                        status = "stopped"
                        break
                    result = await detector.call({"op": control.op})
                if result.get("speech_started"):
                    await send(
                        {
                            "type": "speech_started",
                            "received_sample": result["received_samples"],
                        }
                    )
                for segment in result.get("segments", []):
                    try:
                        queue.put_nowait(segment)
                    except asyncio.QueueFull:
                        await send(
                            {
                                "type": "error",
                                "code": "voice_turn_queue_full",
                                "message": "Transcription is still busy; this utterance was not queued. Retry after the current transcript.",
                            }
                        )
        except (SireError, ValueError, TimeoutError) as exc:
            status = "error"
            await send(
                {
                    "type": "error",
                    "code": getattr(exc, "code", "voice_session_error"),
                    "message": (
                        exc.message
                        if isinstance(exc, SireError)
                        else "Voice control failed or reached its time limit."
                    ),
                }
            )
        except WebSocketDisconnect:
            status = "disconnected"
        finally:
            closing.set()
            if current.get("cancel") is not None:
                current["cancel"].set()
            if status in {"starting", "listening"}:
                status = "interrupted"
            active.discard(conversation_id)
            with anyio.CancelScope(shield=True):
                if current.get("cancel") is not None:
                    try:
                        await asyncio.wait_for(asyncio.shield(task), 5)
                    except TimeoutError:
                        task.cancel()
                else:
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await detector.close()
                metadata["received_pcm_sha256"] = digest.hexdigest()
                save()
                try:
                    await send({"type": "closed", "status": status})
                    await websocket.close()
                except (RuntimeError, WebSocketDisconnect):
                    LOGGER.debug("Voice socket was already closed")
    finally:
        active.discard(conversation_id)
