"""Versioned chat-first API with independent prediction routes and a single SPA host."""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.exceptions import HTTPException
from starlette.responses import Response

from app.chat.service import ChatService
from app.orchestration.workspace import InvestigationContext
from app.orchestration.planner import investigation_requested
from app.orchestration.case_context import recall_requested, status_requested
from app.evidence.ledger import Ledger
from app.api.intelligence import router as intelligence_router
from app.api.specialists import router as specialist_router
from app.voice.sessions import router as voice_session_router
from app.core import config
from app.core.errors import SireError
from app.core.runtime_identity import source_identity
from app.investigation.engine import investigate
from app.investigation.schemas import Case, EvidenceItem
from app.investigation.jobs import InvestigationJob, InvestigationJobs, TERMINAL
from app.knowledge import ingestion
from app.prediction import hub, service, telemetry
from app.prediction.policy import models as production_models
from app.providers.adapter import OllamaAdapter
from app.storage.database import Store

LOGGER = logging.getLogger(__name__)
Dataset = Literal["FD001", "FD002", "FD003", "FD004"]


class Title(BaseModel):
    """A locally persisted conversation title."""

    title: str = Field(default="New chat", min_length=1, max_length=100)


class PredictionRequest(BaseModel):
    """Explicit dataset/model/source; no implicit FD001 substitution."""

    model_config = ConfigDict(extra="forbid")
    dataset: Dataset
    model_id: str = Field(max_length=160)
    asset_id: str | None = Field(default=None, max_length=100)
    attachment_id: str | None = Field(default=None, max_length=100)
    unit_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def one_source(self) -> "PredictionRequest":
        """Refuse missing or ambiguous source selection before inference."""
        if bool(self.asset_id) == bool(self.attachment_id):
            raise ValueError("Exactly one source required")
        return self


class CompareRequest(BaseModel):
    """Run a bounded list independently and report each failure honestly."""

    dataset: Dataset
    model_ids: list[str] = Field(min_length=2, max_length=4)
    asset_id: str | None = None
    attachment_id: str | None = None
    unit_id: int | None = Field(default=None, ge=1)


class ChatRequest(BaseModel):
    """Text and explicit evidence references; no dataset field is required for chat."""

    model_config = ConfigDict(extra="forbid")
    conversation_id: str = Field(max_length=100)
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex, max_length=100)
    content: str = Field(default="", max_length=8000)
    attachment_ids: list[str] = Field(default_factory=list, max_length=6)
    model: str | None = Field(default=None, max_length=120)
    mode: Literal["chat", "investigate"] = "chat"
    prediction_id: str | None = Field(default=None, max_length=100)
    linked_asset: bool = False
    facility_case_id: str | None = Field(default=None, max_length=100)
    context: InvestigationContext | None = None
    voice_response: bool = False
    background_if_deep: bool = False
    input_audio_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def has_input(self) -> "ChatRequest":
        """Accept image-only input but reject an empty turn."""
        if (
            not self.content.strip()
            and not self.attachment_ids
            and not self.prediction_id
            and not self.facility_case_id
        ):
            raise ValueError("Empty message")
        return self


class CancelRequest(BaseModel):
    """Cancellation targets a known opaque request ID."""

    request_id: str = Field(max_length=100)
    reason: Literal[
        "operator_stop",
        "voice_user_interrupt",
        "voice_new_turn",
        "voice_session_stop",
        "client_disconnect",
    ] = "operator_stop"


def error(code: str, message: str, status: int) -> JSONResponse:
    """Return a uniform public error without exposing input contents or local paths."""
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": {},
                "request_id": uuid.uuid4().hex,
            }
        },
    )


def create_app(
    state_dir: Path | None = None,
    provider: OllamaAdapter | None = None,
    probe_model: bool = True,
) -> FastAPI:
    """Create an independently testable API; production performs a real startup model probe."""
    directory = state_dir or config.STATE

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.store = Store(directory / "sire.sqlite3")
        Ledger(application.state.store)
        application.state.chat = ChatService(application.state.store, provider)
        application.state.investigation_jobs = InvestigationJobs(
            application.state.store, provider
        )
        application.state.voice_sessions = set()
        application.state.specialist_calls = {}
        application.state.ml_ready = False
        if probe_model:
            try:
                selected = next(
                    row
                    for row in hub.catalog()
                    if row["dataset"] == "FD001" and row["default"]
                )
                await asyncio.to_thread(
                    hub.predict,
                    selected["model_id"],
                    "FD001",
                    telemetry.asset_history("FD001-ENGINE-001", "FD001"),
                )
                application.state.ml_ready = True
            except Exception:
                LOGGER.exception("Consolidated model startup probe failed")
        yield
        from app.core.worker_pool import close_workers

        for event in application.state.chat.jobs.values():
            event.set()
        for event in application.state.specialist_calls.values():
            event.set()
        await application.state.investigation_jobs.close()
        await asyncio.to_thread(close_workers)

    application = FastAPI(
        title="SIRE chat and prediction API", version="4.7.0", lifespan=lifespan
    )
    application.state.runtime_identity = source_identity(config.ROOT, config.WEB_DIST)
    application.include_router(intelligence_router)
    application.include_router(specialist_router)
    application.include_router(voice_session_router)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.SETTINGS["cors_origins"],
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @application.middleware("http")
    async def body_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Bound multipart and JSON bytes before parsing, including chunked bodies."""
        if request.method in {"POST", "PATCH"}:
            chunks, total = [], 0
            async for chunk in request.stream():
                total += len(chunk)
                if total > config.SETTINGS["max_upload_bytes"] + 65536:
                    return error(
                        "upload_too_large", "Request exceeds the upload limit.", 413
                    )
                chunks.append(chunk)
            request._body = b"".join(chunks)
        return await call_next(request)

    @application.exception_handler(SireError)
    async def domain_error(request: Request, exc: SireError) -> JSONResponse:
        """Expose only typed public domain diagnostics."""
        return error(exc.code, exc.message, exc.status)

    @application.exception_handler(RequestValidationError)
    async def schema_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Do not reflect private message text in validation errors."""
        return error("invalid_request", "Request does not match the API contract.", 422)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        """Use the error envelope for missing routes and methods."""
        return error(
            "http_error",
            "Requested resource or method is unavailable.",
            exc.status_code,
        )

    @application.exception_handler(Exception)
    async def unknown_error(request: Request, exc: Exception) -> JSONResponse:
        """Keep private provider payloads out of both UI and ordinary logs."""
        LOGGER.error("API failure type=%s", type(exc).__name__)
        return error(
            "internal_error", "Operation failed; consult the local diagnostic log.", 500
        )

    @application.get("/api/v1/health")
    @application.get("/api/health", include_in_schema=False)
    def health(request: Request) -> dict:
        """Differentiate server liveness, startup inference and installed-provider capabilities."""
        return {
            "status": "ok",
            "contract_version": "2.0",
            "application_version": application.version,
            "loaded_source_sha256": request.app.state.runtime_identity,
            "ml_ready": request.app.state.ml_ready,
            **request.app.state.chat.provider.health(),
            "mode": "local",
            "hosted_providers": "disabled",
        }

    @application.get("/api/v1/providers")
    def providers(request: Request) -> dict:
        """Discover installed models rather than showing a hard-coded provider list."""
        adapter = request.app.state.chat.provider
        try:
            rows = adapter.list_models()
        except SireError:
            rows = []
        return {
            "provider": "ollama",
            "models": rows,
            "health": adapter.health(),
            "configured_text": config.SETTINGS["text_model"],
            "configured_vision": config.SETTINGS["vision_model"],
            "retrieval": "local_lexical",
            "embedding_model": config.SETTINGS.get("embedding_model"),
        }

    @application.get("/api/v1/conversations")
    def conversations(request: Request) -> dict:
        """List real saved chat sessions."""
        return {"conversations": request.app.state.store.list_conversations()}

    @application.post("/api/v1/conversations")
    def create_conversation(body: Title, request: Request) -> dict:
        """Create a persisted empty conversation."""
        return request.app.state.store.create_conversation(body.title)

    @application.get("/api/v1/conversations/{identifier}")
    def conversation(identifier: str, request: Request) -> dict:
        """Reload messages and attachment metadata across process restarts."""
        store = request.app.state.store
        return {
            **store.conversation(identifier),
            "messages": store.messages(identifier),
            "attachments": store.attachments(identifier),
        }

    @application.patch("/api/v1/conversations/{identifier}")
    def rename(identifier: str, body: Title, request: Request) -> dict:
        """Rename a saved conversation."""
        request.app.state.store.rename(identifier, body.title)
        return request.app.state.store.conversation(identifier)

    @application.delete("/api/v1/conversations/{identifier}")
    def delete(identifier: str, request: Request, confirm: bool = False) -> dict:
        """Require confirmation and delete only the conversation's own local files."""
        if identifier in request.app.state.chat.active_conversations:
            raise SireError(
                "chat_busy",
                "Stop the active response before deleting this conversation.",
                409,
            )
        if any(
            job.status not in TERMINAL
            for job in request.app.state.investigation_jobs.list(identifier)
        ):
            raise SireError(
                "investigation_busy",
                "Stop the background investigation before deleting this conversation.",
                409,
            )
        for raw in request.app.state.store.delete(identifier, confirm):
            path = Path(raw).resolve()
            base = (directory / "attachments").resolve()
            if path.is_relative_to(base):
                path.unlink(missing_ok=True)
        return {"deleted": True}

    @application.post("/api/v1/attachments")
    @application.post("/api/v1/knowledge/ingest")
    async def attach(
        request: Request,
        conversation_id: str = Form(...),
        file: UploadFile = File(...),
        dataset: Dataset | None = Form(None),
        compatible_cmapss: bool = Form(False),
        media_request_id: str | None = Form(None, max_length=100),
    ) -> dict:
        """Persist validated local image/document/CSV evidence with randomized storage names."""
        content = await file.read(config.SETTINGS["max_upload_bytes"] + 1)
        if dataset and (file.filename or "").lower().endswith((".csv", ".txt")):
            from app.prediction.datasets import ingest as ingest_prediction

            return await asyncio.to_thread(
                ingest_prediction,
                request.app.state.store,
                conversation_id,
                file.filename,
                content,
                dataset,
                compatible_cmapss,
            )
        return await asyncio.to_thread(
            ingestion.ingest,
            request.app.state.store,
            conversation_id,
            file.filename or "attachment",
            content,
            dataset,
            compatible_cmapss,
            media_request_id,
        )

    @application.get("/api/v1/attachments/{identifier}/content")
    def attachment_content(identifier: str, request: Request) -> FileResponse:
        """Serve only catalogued local evidence; no arbitrary filesystem paths."""
        item = request.app.state.store.attachment(identifier)
        if item["kind"] == "image":
            return FileResponse(
                item["path"],
                media_type="image/jpeg",
                headers={"X-Content-Type-Options": "nosniff"},
            )
        if item["mime"] == "application/pdf":
            return FileResponse(
                item["path"],
                media_type="application/pdf",
                filename=item["name"],
                content_disposition_type="inline",
                headers={"X-Content-Type-Options": "nosniff"},
            )
        return FileResponse(
            item["path"],
            media_type="application/octet-stream",
            filename=item["name"],
            headers={"X-Content-Type-Options": "nosniff"},
        )

    @application.get("/api/v1/knowledge/sources")
    def sources(conversation_id: str, request: Request) -> dict:
        """Return actual document and CSV sources for one chat."""
        store = request.app.state.store
        return {
            "sources": store.attachments(conversation_id),
            "chunks": store.rows(
                "SELECT id,attachment_id,locator,text FROM chunks WHERE conversation_id=?",
                (conversation_id,),
            ),
        }

    @application.post(
        "/api/v1/investigation-jobs", response_model=InvestigationJob, status_code=202
    )
    async def start_investigation_job(
        body: ChatRequest, request: Request
    ) -> InvestigationJob:
        """Start a bounded durable job while leaving the ordinary chat endpoint usable."""
        value = body.model_dump(exclude={"background_if_deep"})
        value["mode"] = "investigate"
        return request.app.state.investigation_jobs.submit(value)

    @application.get(
        "/api/v1/investigation-jobs", response_model=list[InvestigationJob]
    )
    def investigation_jobs(
        conversation_id: str, request: Request
    ) -> list[InvestigationJob]:
        """Reload actual job state after navigation; scope every record to one conversation."""
        return request.app.state.investigation_jobs.list(conversation_id)

    @application.get(
        "/api/v1/investigation-jobs/{identifier}", response_model=InvestigationJob
    )
    def investigation_job(
        identifier: str, conversation_id: str, request: Request
    ) -> InvestigationJob:
        """Read durable progress and real run/message references without waiting for inference."""
        return request.app.state.investigation_jobs.get(identifier, conversation_id)

    @application.post(
        "/api/v1/investigation-jobs/{identifier}/cancel",
        response_model=InvestigationJob,
    )
    def cancel_investigation_job(
        identifier: str, conversation_id: str, request: Request
    ) -> InvestigationJob:
        """Cancel only the selected background request, preserving completed sources and turns."""
        return request.app.state.investigation_jobs.cancel(identifier, conversation_id)

    @application.post("/api/v1/chat/message", response_model=None)
    async def message(
        body: ChatRequest, request: Request
    ) -> StreamingResponse | JSONResponse:
        """SSE transports actual upstream deltas and actual progressive tool events."""
        chat = request.app.state.chat
        store = request.app.state.store
        store.conversation(body.conversation_id)
        for identifier in body.attachment_ids:
            store.attachment(identifier, body.conversation_id)
        if body.prediction_id:
            store.result("predictions", body.prediction_id)
        from app.chat.conversation import input_audio

        effective, _ = input_audio(
            store,
            body.conversation_id,
            [
                store.attachment(identifier, body.conversation_id)
                for identifier in body.attachment_ids
            ],
            body.content,
            body.input_audio_id,
            body.voice_response,
        )
        if (
            body.background_if_deep
            and not (
                body.mode == "chat"
                and (
                    status_requested(body.content)
                    or (not body.attachment_ids and recall_requested(body.content))
                )
            )
            and investigation_requested(
                body.content, body.mode == "investigate", bool(effective)
            )
        ):
            value = body.model_dump(exclude={"background_if_deep"})
            value["mode"] = "investigate"
            job = request.app.state.investigation_jobs.submit(value)
            return JSONResponse(
                status_code=202,
                content={
                    "type": "investigation_job",
                    "job": job.model_dump(mode="json"),
                },
            )
        if body.conversation_id in chat.active_conversations:
            raise SireError(
                "chat_busy", "This conversation already has an active response.", 409
            )

        async def stream() -> AsyncIterator[str]:
            try:
                async for event in chat.events(
                    **body.model_dump(exclude={"background_if_deep"})
                ):
                    if await request.is_disconnected():
                        chat.cancel(body.request_id, "client_disconnect")
                        break
                    yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
            except SireError as exc:
                yield "data: " + json.dumps(
                    {"type": "error", "code": exc.code, "message": exc.message}
                ) + "\n\n"

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @application.post("/api/v1/chat/cancel")
    def cancel(body: CancelRequest, request: Request) -> dict:
        """A current tool may finish; cancelled requests start no later tools."""
        return {
            "cancellation_requested": request.app.state.chat.cancel(
                body.request_id, body.reason
            )
        }

    @application.post("/api/v1/investigations")
    async def new_case(body: Case, request: Request) -> dict:
        """Use only evidence already persisted by this server, never client-invented measurements."""
        store = request.app.state.store
        known = []
        for row in store.messages(body.conversation_id):
            known.extend(row["metadata"].get("evidence", []))
        source = {
            row["id"]: EvidenceItem.model_validate(row).model_dump() for row in known
        }
        if any(
            item.id not in source or item.model_dump() != source[item.id]
            for item in body.evidence
        ):
            raise SireError(
                "untrusted_evidence",
                "Use evidence collected in this conversation; client assertions cannot become verified measurements.",
            )
        report = await investigate(store, body, asyncio.Event())
        payload = report.model_dump()
        store.save_result("cases", payload, body.conversation_id)
        return payload

    @application.get("/api/v1/investigations/{identifier}")
    def case_detail(identifier: str, request: Request) -> dict:
        """Read the persisted structured case and its evidence audit trail."""
        return request.app.state.store.result("cases", identifier)

    @application.get("/api/v1/investigations")
    def cases(request: Request) -> dict:
        """List actual persisted cases, without inventing sample incidents."""
        return {
            "cases": request.app.state.store.rows(
                "SELECT id,conversation_id,created_at FROM cases ORDER BY created_at DESC"
            )
        }

    @application.get("/api/v1/predictions/datasets")
    def datasets() -> dict:
        """List all supported C-MAPSS subsets and source-derived assets."""
        return {
            "datasets": [
                {
                    "id": dataset,
                    "description": "NASA C-MAPSS simulated turbofan histories",
                    "assets": telemetry.assets(dataset),
                }
                for dataset in telemetry.DATASETS
            ]
        }

    @application.get("/api/v1/predictions/models")
    @application.get("/api/v1/models")
    @application.get("/api/models", include_in_schema=False)
    def models(dataset: Dataset | None = None, purpose: str | None = None) -> dict:
        """Expose tested, failed and untested routes distinctly across all seeds."""
        return {
            "models": [
                row
                for row in production_models()
                if (dataset is None or row["dataset"] == dataset)
                and (purpose is None or row["purpose"] == purpose)
            ]
        }

    @application.post("/api/v1/predictions/run")
    def prediction(body: PredictionRequest, request: Request) -> dict:
        """Run one actual native RUL model and save the result as an attachable artifact."""
        return service.run(request.app.state.store, **body.model_dump())

    @application.post("/api/v1/predictions/upload")
    async def prediction_upload(
        request: Request,
        file: UploadFile = File(...),
        dataset: Dataset = Form(...),
        compatible_cmapss: bool = Form(False),
    ) -> dict:
        """Independent CSV ingestion does not require creating a chat."""
        from app.prediction.datasets import ingest as ingest_prediction

        return await asyncio.to_thread(
            ingest_prediction,
            request.app.state.store,
            None,
            file.filename,
            await file.read(config.SETTINGS["max_upload_bytes"] + 1),
            dataset,
            compatible_cmapss,
        )

    @application.get("/api/v1/predictions/uploads/{identifier}/telemetry")
    def uploaded_sensor_history(
        identifier: str, dataset: Dataset, request: Request, unit_id: int | None = None
    ) -> dict:
        """Show only the uploaded validated history when it is the selected source."""
        from app.prediction.datasets import history

        frame = history(request.app.state.store, identifier, dataset, unit_id)
        return {
            "records": frame.to_dict("records"),
            "source": identifier,
            "data_origin": "user_declared_cmapss",
        }

    @application.post("/api/v1/predictions/anomaly")
    def anomaly(body: PredictionRequest, request: Request) -> dict:
        """Expose experimental anomaly/health output with separate semantics."""
        return service.run(request.app.state.store, **body.model_dump(), task="anomaly")

    @application.post("/api/v1/predictions/compare")
    def compare(body: CompareRequest, request: Request) -> dict:
        """Each selected model gets the same source and an individual result/error."""
        results = []
        for identifier in dict.fromkeys(body.model_ids):
            try:
                results.append(
                    {
                        "model_id": identifier,
                        "result": service.run(
                            request.app.state.store,
                            body.dataset,
                            identifier,
                            body.asset_id,
                            body.attachment_id,
                            unit_id=body.unit_id,
                        ),
                    }
                )
            except SireError as exc:
                results.append(
                    {
                        "model_id": identifier,
                        "error": {"code": exc.code, "message": exc.message},
                    }
                )
        return {"results": results}

    @application.get("/api/v1/predictions/assets/{dataset}/{asset_id}/telemetry")
    def sensor_history(dataset: Dataset, asset_id: str) -> dict:
        """Read the selected engine's actual matched source readings."""
        return telemetry.telemetry(asset_id, dataset)

    @application.get("/api/v1/predictions/results/{identifier}")
    def prediction_detail(identifier: str, request: Request) -> dict:
        """Retrieve an immutable saved prediction without rerunning a model."""
        return request.app.state.store.result("predictions", identifier)

    static = config.WEB_DIST
    if (static / "static").is_dir():
        application.mount(
            "/static", StaticFiles(directory=static / "static"), name="static"
        )

    @application.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> Response:
        """Support actual browser routes while refusing unknown API paths."""
        if path.startswith("api/") or not (static / "index.html").is_file():
            raise SireError("not_found", "Route not found.", 404)
        return FileResponse(static / "index.html")

    return application


app = create_app()
