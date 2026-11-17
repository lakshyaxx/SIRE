"""Durable bounded background investigations using the real shared chat/tool pipeline."""

import asyncio
import uuid
from typing import Literal
from pydantic import BaseModel, Field
from app.chat.service import ChatService
from app.core.config import SETTINGS
from app.core.errors import SireError
from app.evidence.ledger import digest
from app.providers.adapter import OllamaAdapter
from app.providers.resources import PRIORITY
from app.storage.database import Store, now

JobStatus = Literal[
    "queued", "running", "complete", "partial", "error", "cancelled", "interrupted"
]
TERMINAL = {"complete", "partial", "error", "cancelled", "interrupted"}


class InvestigationJob(BaseModel):
    """A persisted lifecycle and actual bounded event history, separate from hidden reasoning."""

    id: str
    conversation_id: str
    request_id: str
    status: JobStatus = "queued"
    created_at: str
    updated_at: str
    events: list[dict] = Field(default_factory=list)
    events_total: int = 0
    events_trimmed: int = 0
    run_id: str | None = None
    assistant_message_id: str | None = None
    error: dict | None = None


class InvestigationJobs:
    """Own asynchronous tasks in a single local API worker; never resume stale jobs silently."""

    def __init__(self, store: Store, provider: OllamaAdapter | None = None) -> None:
        self.store, self.provider = store, provider
        self.tasks: dict[str, asyncio.Task] = {}
        self.services: dict[str, ChatService] = {}
        with store.connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS v45_jobs(id TEXT PRIMARY KEY,conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,request_id TEXT UNIQUE,body_sha256 TEXT,payload TEXT)"
            )
        for row in store.rows("SELECT payload FROM v45_jobs"):
            job = InvestigationJob.model_validate_json(row["payload"])
            if job.status not in TERMINAL:
                job.status = "interrupted"
                job.error = {
                    "code": "process_restarted",
                    "message": "The previous process ended. Completed evidence and messages are retained; submit a new request to continue.",
                }
                self._save(job)

    def _save(self, job: InvestigationJob) -> None:
        job.updated_at = now()
        with self.store.connection() as db:
            db.execute(
                "UPDATE v45_jobs SET payload=? WHERE id=?",
                (job.model_dump_json(), job.id),
            )

    def get(self, identifier: str, conversation_id: str) -> InvestigationJob:
        """Resolve only a job belonging to the explicitly selected conversation."""
        rows = self.store.rows(
            "SELECT payload FROM v45_jobs WHERE id=? AND conversation_id=?",
            (identifier, conversation_id),
        )
        if not rows:
            raise SireError(
                "investigation_job_missing",
                "Investigation job not found in this conversation.",
                404,
            )
        return InvestigationJob.model_validate_json(rows[0]["payload"])

    def list(self, conversation_id: str) -> list[InvestigationJob]:
        """Return bounded saved lifecycle records; active tasks are never inferred from a spinner."""
        self.store.conversation(conversation_id)
        return [
            InvestigationJob.model_validate_json(row["payload"])
            for row in self.store.rows(
                "SELECT payload FROM v45_jobs WHERE conversation_id=? ORDER BY rowid DESC LIMIT 20",
                (conversation_id,),
            )
        ]

    def submit(self, request: dict) -> InvestigationJob:
        """Save before scheduling; enforce idempotence, conversation isolation and global limits."""
        cid = request["conversation_id"]
        self.store.conversation(cid)
        for identifier in request["attachment_ids"]:
            self.store.attachment(identifier, cid)
        signature = digest(request)
        prior = self.store.rows(
            "SELECT id,body_sha256,conversation_id FROM v45_jobs WHERE request_id=?",
            (request["request_id"],),
        )
        if prior:
            if (
                prior[0]["body_sha256"] != signature
                or prior[0]["conversation_id"] != cid
            ):
                raise SireError(
                    "request_id_conflict",
                    "This request ID was already used for different input.",
                    409,
                )
            return self.get(prior[0]["id"], cid)
        if any(job.status not in TERMINAL for job in self.list(cid)):
            raise SireError(
                "investigation_busy",
                "This conversation already has a background investigation.",
                409,
            )
        if len(self.tasks) >= SETTINGS.get("background_investigation_limit", 1):
            raise SireError(
                "investigation_capacity",
                "The local investigation queue is full; retry after the current job ends.",
                429,
            )
        job = InvestigationJob(
            id=uuid.uuid4().hex,
            conversation_id=cid,
            request_id=request["request_id"],
            created_at=now(),
            updated_at=now(),
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO v45_jobs VALUES(?,?,?,?,?)",
                (job.id, cid, job.request_id, signature, job.model_dump_json()),
            )
        self.tasks[job.id] = asyncio.create_task(self._run(job, request))
        self.tasks[job.id].add_done_callback(lambda _: self.tasks.pop(job.id, None))
        return job

    async def _run(self, job: InvestigationJob, request: dict) -> None:
        priority_token = PRIORITY.set(10)
        service = ChatService(self.store, self.provider)
        self.services[job.id] = service
        job.status = "running"
        self._save(job)
        try:
            async for event in service.events(**request):
                job.events_total += 1
                job.events.append(event)
                limit = SETTINGS.get("background_job_event_limit", 256)
                if len(job.events) > limit:
                    job.events.pop(0)
                    job.events_trimmed += 1
                if event["type"] == "plan":
                    job.run_id = event["run_id"]
                elif event["type"] == "done":
                    job.status = event["status"]
                    job.error = event["metadata"].get("error")
                    rows = self.store.rows(
                        "SELECT id FROM messages WHERE conversation_id=? AND role='assistant' AND json_extract(metadata,'$.orchestration.run_id')=? ORDER BY rowid DESC LIMIT 1",
                        (job.conversation_id, job.run_id),
                    )
                    job.assistant_message_id = rows[0]["id"] if rows else None
                self._save(job)
            if job.status not in TERMINAL:
                job.status = "error"
                job.error = {
                    "code": "incomplete_event_stream",
                    "message": "The investigation ended without a terminal event; no completion is inferred.",
                }
        except asyncio.CancelledError:
            job.status = "cancelled"
        except Exception as exc:
            job.status = "error"
            job.error = {
                "code": getattr(exc, "code", "investigation_failed"),
                "message": "The investigation failed. Completed evidence and partial messages are retained.",
            }
        finally:
            self._save(job)
            self.services.pop(job.id, None)
            self.tasks.pop(job.id, None)
            PRIORITY.reset(priority_token)

    def cancel(self, identifier: str, conversation_id: str) -> InvestigationJob:
        """Cancel only the chosen job; ordinary chat in the same conversation stays independent."""
        job = self.get(identifier, conversation_id)
        if job.status not in TERMINAL:
            service = self.services.get(identifier)
            if service:
                service.cancel(job.request_id)
            task = self.tasks.get(identifier)
            if task:
                task.cancel()
            job.status = "cancelled"
            self._save(job)
        return job

    async def close(self) -> None:
        """Finish task cancellation before API shutdown without deleting durable records."""
        tasks = list(self.tasks.values())
        for identifier in list(self.tasks):
            rows = self.store.rows(
                "SELECT conversation_id FROM v45_jobs WHERE id=?", (identifier,)
            )
            if rows:
                self.cancel(identifier, rows[0]["conversation_id"])
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
