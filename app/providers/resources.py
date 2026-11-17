"""Bounded cancellable local model scheduling, separate from cognitive task selection."""

import asyncio
import os
from collections import deque
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from pathlib import Path
import threading
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any
from app.core.config import ROOT, SETTINGS
from app.core.errors import SireError

PRIORITY: ContextVar[int] = ContextVar("sire_model_priority", default=5)


class ResourceScheduler:
    """Serialize heavy work across threads/processes; queue limits and metrics are per API worker."""

    def __init__(
        self, path: Path, queue_limit: int = 8, wait_seconds: float = 180
    ) -> None:
        if queue_limit < 1 or wait_seconds <= 0:
            raise ValueError("A positive queue capacity and wait budget are required")
        self.path, self.queue_limit, self.wait_seconds = path, queue_limit, wait_seconds
        self.lock = threading.Lock()
        self.waiting: dict[str, dict] = {}
        self.active: dict[str, dict] = {}
        self.history: deque[dict] = deque(maxlen=100)

    def _enqueue(
        self, capability: str, priority: int | None, model: str | None
    ) -> dict:
        with self.lock:
            if len(self.waiting) >= self.queue_limit:
                raise SireError(
                    "model_queue_full",
                    "The local model queue is full; retry shortly.",
                    429,
                )
            entry = {
                "id": uuid.uuid4().hex,
                "capability": capability,
                "model": model,
                "priority": PRIORITY.get() if priority is None else priority,
                "queued_at_monotonic": time.monotonic(),
            }
            self.waiting[entry["id"]] = entry
            return entry

    def _file_lock(self) -> Any | None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        try:
            if self.path.stat().st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return stream
        except (OSError, BlockingIOError):
            stream.close()
            return None

    def _grant(self, entry: dict) -> Any | None:
        with self.lock:
            if (
                self.active
                or min(
                    self.waiting.values(),
                    key=lambda row: (row["priority"], row["queued_at_monotonic"]),
                )["id"]
                != entry["id"]
            ):
                return None
            stream = self._file_lock()
            if stream is None:
                return None
            self.waiting.pop(entry["id"])
            entry["started_at_monotonic"] = time.monotonic()
            entry["queue_seconds"] = (
                entry["started_at_monotonic"] - entry["queued_at_monotonic"]
            )
            self.active[entry["id"]] = entry
            return stream

    def _finish(self, entry: dict, stream: Any | None) -> None:
        with self.lock:
            self.waiting.pop(entry["id"], None)
            self.active.pop(entry["id"], None)
            if stream is not None:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                stream.close()
            finished = {**entry, "ended_at_monotonic": time.monotonic()}
            finished["total_seconds"] = (
                finished["ended_at_monotonic"] - entry["queued_at_monotonic"]
            )
            self.history.append(finished)

    def _check(self, entry: dict, cancelled: Any) -> None:
        if cancelled is not None and cancelled.is_set():
            raise SireError(
                "resource_cancelled", "The queued model operation was cancelled.", 409
            )
        if time.monotonic() - entry["queued_at_monotonic"] >= self.wait_seconds:
            raise SireError(
                "model_queue_timeout",
                "The local model queue reached its wait budget; no inference was substituted.",
                503,
            )

    @contextmanager
    def lease(
        self,
        capability: str,
        *,
        cancelled: Any = None,
        priority: int | None = None,
        model: str | None = None,
    ) -> Iterator[dict]:
        """Grant one real OS-locked inference slot and release it on every terminal path."""
        entry = self._enqueue(capability, priority, model)
        stream = None
        try:
            while stream is None:
                self._check(entry, cancelled)
                stream = self._grant(entry)
                if stream is None:
                    time.sleep(0.025)
            yield entry
        finally:
            self._finish(entry, stream)

    @asynccontextmanager
    async def async_lease(
        self,
        capability: str,
        *,
        cancelled: Any = None,
        priority: int | None = None,
        model: str | None = None,
    ) -> AsyncIterator[dict]:
        """Wait without blocking the API loop or leaking a late-acquired thread lease on cancellation."""
        entry = self._enqueue(capability, priority, model)
        stream = None
        try:
            while stream is None:
                if cancelled is not None and cancelled.is_set():
                    raise asyncio.CancelledError()
                self._check(entry, None)
                stream = self._grant(entry)
                if stream is None:
                    await asyncio.sleep(0.025)
            yield entry
        finally:
            self._finish(entry, stream)

    def snapshot(self) -> dict:
        """Expose actual local queue/lease observations; residency still comes from provider health."""
        with self.lock:
            return {
                "heavy_slots": 1,
                "scope": "OS file lock across cooperating SIRE processes; queue/metrics per worker",
                "active": list(self.active.values()),
                "waiting": list(self.waiting.values()),
                "recent": list(self.history),
            }


SCHEDULER = ResourceScheduler(
    ROOT / ".runtime/model-resource.lock",
    SETTINGS.get("model_queue_limit", 8),
    SETTINGS.get("model_queue_wait_seconds", 180),
)
