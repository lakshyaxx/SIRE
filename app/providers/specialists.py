"""Existing media/document specialists bound to the shared typed registry."""

import asyncio
import base64
import hashlib
from threading import Event
from pydantic import BaseModel, ConfigDict, Field
from app.core.config import SETTINGS
from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.orchestration.runtime import Invocation, Plan, Registry, Runner
from app.providers.contracts import DocumentOutput, SpeechOutput, VideoOutput
from app.storage.database import Store


class DocumentInput(BaseModel):
    """Extract bounded original source chunks from one owned attachment."""

    model_config = ConfigDict(extra="forbid")
    conversation_id: str
    attachment_id: str
    max_characters: int = Field(default=4000, ge=100, le=20000)
    include_statistics: bool = True


class SpeechInput(BaseModel):
    """Bounded synthesis using an actual voice in the installed model."""

    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1200)
    voice_id: int = Field(default=0, ge=0, le=255)
    speed: float = Field(default=1, ge=0.5, le=2)


class VideoInput(BaseModel):
    """Inspect stored sampled frames, preserving each original decoder position."""

    model_config = ConfigDict(extra="forbid")
    conversation_id: str
    attachment_id: str
    text: str = Field(
        default="Describe visible features and limitations.", max_length=8000
    )


def register_specialists(
    registry: Registry, store: Store, cancelled: asyncio.Event
) -> None:
    """Add actual adapters to the existing registry; never create another scheduler."""
    from app.orchestration.tools import ImageInput

    async def document(args: DocumentInput) -> dict:
        item = store.attachment(args.attachment_id, args.conversation_id)
        from app.evidence.integrity import read_verified, validate_chunks

        content = await asyncio.to_thread(read_verified, item)
        if item["kind"] not in {"document", "csv"}:
            raise SireError(
                "document_required", "Choose an extracted document or table attachment."
            )
        chunks = store.rows(
            "SELECT * FROM chunks WHERE attachment_id=? AND conversation_id=? ORDER BY rowid",
            (args.attachment_id, args.conversation_id),
        )
        from pathlib import Path

        suffix = Path(item["name"]).suffix.lower()
        extraction = "stored_deterministic_extraction"
        if not chunks and suffix == ".csv":
            from app.evidence.formats import sections

            extraction = "on_demand_deterministic_csv"
            chunks = []
            for locator, text in sections(content, ".csv"):
                chunks.append({"id": None, "text": text, "locator": locator})
        elif chunks:
            await asyncio.to_thread(
                validate_chunks, store, args.conversation_id, chunks
            )
        if not chunks:
            raise SireError(
                "document_text_unavailable",
                "No deterministic text extraction is available.",
                422,
            )
        selected, used = [], 0
        for chunk in chunks:
            remaining = args.max_characters - used
            if remaining <= 0:
                break
            text = chunk["text"][:remaining]
            if chunk["id"] is None:
                chunk["id"] = (
                    Ledger(store)
                    .add(
                        "real_uploaded",
                        item["name"],
                        {"text": chunk["text"], "locator": chunk["locator"]},
                        {"attachment_id": item["id"], "locator": chunk["locator"]},
                        content_sha256=item["sha256"],
                        available_at=item["created_at"],
                        method="deterministic_csv_record",
                        quality="uploaded_source_authenticity_unverified",
                    )
                    .id
                )
            Ledger(store).resolve(chunk["id"])
            selected.append(
                {
                    "evidence_id": chunk["id"],
                    "attachment_id": item["id"],
                    "locator": chunk["locator"],
                    "text": text,
                    "excerpted": len(text) != len(chunk["text"]),
                }
            )
            used += len(text)
        result = {
            "sections": selected,
            "evidence_ids": [s["evidence_id"] for s in selected],
            "attachment_id": item["id"],
            "total_chunks": len(chunks),
            "selected_characters": used,
            "extraction": extraction,
        }
        if args.include_statistics and suffix in {".csv", ".xlsx"}:
            from app.evidence.tabular import summarize

            tables = await asyncio.to_thread(summarize, content, suffix)
            record = Ledger(store).add(
                "real_uploaded",
                item["name"],
                {"tables": tables},
                {"attachment_id": item["id"]},
                content_sha256=item["sha256"],
                available_at=item["created_at"],
                method="deterministic_numeric_columns_v1",
                quality="uploaded_source_authenticity_unverified",
            )
            result["tables"] = tables
            result["statistics_evidence_id"] = record.id
            result["evidence_ids"].append(record.id)
        return result

    async def speech(args: SpeechInput) -> dict:
        from app.media.runtime import run

        stop = Event()
        try:
            output = await asyncio.to_thread(run, "tts", args.model_dump(), None, stop)
        finally:
            stop.set()
        audio = {
            "audio_base64": base64.b64encode(output["audio_bytes"]).decode("ascii"),
            "sha256": hashlib.sha256(output["audio_bytes"]).hexdigest(),
            **{
                key: output[key]
                for key in [
                    "sample_rate",
                    "frames",
                    "duration_seconds",
                    "provider",
                    "model",
                    "spoken_text",
                    "warnings",
                ]
            },
            "voice_id": output.get("voice_id", args.voice_id),
            "speed": output.get("speed", args.speed),
            "cache": output.get("cache", {}),
            "phase_timings": output.get("phase_timings", {}),
            "resources": output.get("resources", {}),
            "original_synthesis_resources": output.get(
                "original_synthesis_resources", {}
            ),
            "model_hashes": output.get("model_hashes", {}),
            "worker_lifecycle": output.get("worker_lifecycle", {}),
            "worker_fallback": output.get("worker_fallback", {}),
            "model_reused": output.get("model_reused", False),
        }
        return {"audio": audio, "evidence_ids": []}

    async def video(args: VideoInput) -> dict:
        item = store.attachment(args.attachment_id, args.conversation_id)
        metadata = item["metadata"].get("video", {})
        frames = metadata.get("frames", [])
        if item["kind"] != "video" or not frames:
            raise SireError(
                "video_frames_unavailable", "No real decoded frames are available.", 503
            )
        child = Runner(
            Ledger(store),
            Plan(
                intent="sampled_video_inspection",
                goals=["Inspect only actual sampled frames"],
                tools=[],
                deadline_seconds=SETTINGS.get("chat_budget_seconds", 300),
            ),
            registry,
        )
        inspected, ids = [], []
        try:
            for frame in frames[: SETTINGS["max_visual_calls_per_turn"]]:
                request = ImageInput(
                    conversation_id=args.conversation_id,
                    attachment_id=frame["attachment_id"],
                    text=args.text,
                )
                result = await child.execute(
                    Invocation(
                        tool_id="vision.inspect", arguments=request.model_dump()
                    ),
                    cancelled,
                )
                inspected.append({**frame, **result})
                ids.extend(result["evidence_ids"])
            child.finish("complete")
        except BaseException:
            child.finish("cancelled" if cancelled.is_set() else "error")
            raise
        return {
            "video": {
                "attachment_id": item["id"],
                "child_run_id": child.id,
                "sampling_policy": metadata.get("sampling_policy"),
                "sampled_frames": len(inspected),
                "available_frames": len(frames),
            },
            "frames": inspected,
            "evidence_ids": ids,
            "limitations": [
                "Sampled still frames leave unsampled intervals unobserved.",
                "Visible observations do not establish internal failures or continuous behavior.",
                "Decoder times are source metadata, not independently verified wall-clock timestamps.",
            ],
        }

    registry.register(
        "document.extract",
        DocumentInput,
        document,
        ["document", "conversation_id"],
        output_type=DocumentOutput,
    )
    registry.register(
        "speech.synthesize",
        SpeechInput,
        speech,
        ["text"],
        120,
        output_type=SpeechOutput,
    )
    registry.register(
        "video.inspect",
        VideoInput,
        video,
        ["video", "conversation_id"],
        300,
        output_type=VideoOutput,
    )
    for name, provider_ids in {
        "vision.inspect": ["ollama:" + SETTINGS["vision_model"]],
        "audio.transcript": ["sherpa:asr"],
        "speech.synthesize": ["sherpa:tts"],
        "document.extract": ["local:documents"],
        "knowledge.retrieve": ["local:retrieval"],
        "video.inspect": ["local:video", "ollama:" + SETTINGS["vision_model"]],
        "video.frames": ["local:video"],
        "measurements.profile": ["local:documents"],
        "prediction.run": ["preserved_native:dataset-specific"],
    }.items():
        registry.tools[name][0].provider_ids = provider_ids
