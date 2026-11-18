"""Bounded owned CPU workers with cancellable JSON-file IPC and idle eviction."""

import atexit
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import weakref
from typing import Any
from collections.abc import Callable
from app.core.config import ROOT
from app.core.errors import SireError

_WORKERS: weakref.WeakSet = weakref.WeakSet()
REQUESTS = ROOT / ".runtime/resident_requests"


def terminate_owned(process: subprocess.Popen) -> None:
    """Stop this live owned tree, including the Windows virtualenv launcher child."""
    if process.poll() is None:
        if os.name == "nt":
            # The open process handle pins this PID's identity. Never match names.
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
        else:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def request_file(path: str) -> dict:
    """Read only an owned transient request file; evidence text is never executable."""
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(REQUESTS.resolve()) or not resolved.is_file():
        raise ValueError("Resident request is outside its private directory")
    return json.loads(resolved.read_text(encoding="utf-8"))


def serve(handler: Callable[[dict], dict]) -> None:
    """Serve owned requests; parent pipe closure stops this process even during native work."""
    pending: queue.Queue = queue.Queue(maxsize=1)

    def read() -> None:
        for line in sys.stdin:
            pending.put(json.loads(line))
        # Only the owning parent has this pipe's write end. EOF is cancellation
        # after parent exit, including abrupt API restart; never exit another PID.
        os._exit(0)

    threading.Thread(target=read, daemon=True, name="sire-parent-pipe-watch").start()
    while True:
        descriptor = pending.get()
        result = handler(request_file(descriptor["request_file"]))
        print(
            json.dumps({"id": descriptor["id"], "result": result}, allow_nan=False),
            flush=True,
        )
        del result, descriptor


class WorkerProcess:
    """Retain one lazy model process; never acquire or replace the existing scheduler."""

    def __init__(
        self,
        module: str,
        idle_seconds: float,
        threads: int = 2,
        command: list[str] | None = None,
    ) -> None:
        if idle_seconds <= 0 or threads < 1:
            raise ValueError("Positive residency/thread bounds required")
        self.module, self.idle_seconds, self.threads = module, idle_seconds, threads
        self.command = command
        self.lock = threading.RLock()
        self.process: subprocess.Popen | None = None
        self.responses: queue.Queue = queue.Queue(maxsize=2)
        self.fingerprint: str | None = None
        self.timer: threading.Timer | None = None
        self.active = False
        self.requests = 0
        self.last_used = 0.0
        _WORKERS.add(self)

    def _start(self, fingerprint: str) -> None:
        if self.process and (
            self.process.poll() is not None or self.fingerprint != fingerprint
        ):
            self.close()
        if self.process:
            return
        self.responses = queue.Queue(maxsize=2)
        self.process = subprocess.Popen(
            self.command or [sys.executable, "-m", self.module, "--resident"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env=dict(
                os.environ,
                PYTHONDONTWRITEBYTECODE="1",
                CUDA_VISIBLE_DEVICES="",
                OMP_NUM_THREADS=str(self.threads),
                OPENBLAS_NUM_THREADS=str(self.threads),
                HF_HUB_OFFLINE="1",
                TRANSFORMERS_OFFLINE="1",
            ),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.fingerprint = fingerprint
        self.requests = 0
        process, responses = self.process, self.responses

        def read() -> None:
            try:
                while True:
                    line = process.stdout.readline(16_000_001)
                    if not line or len(line) > 16_000_000:
                        responses.put_nowait(
                            {"ipc_error": "Worker exited or exceeded bounded output"}
                        )
                        return
                    responses.put_nowait(json.loads(line))
            except (OSError, ValueError, queue.Full):
                try:
                    responses.put_nowait({"ipc_error": "Invalid worker protocol"})
                except queue.Full:
                    return

        threading.Thread(
            target=read, daemon=True, name="sire-owned-worker-reader"
        ).start()

    def execute(
        self, payload: dict, cancelled: Any, timeout: float, fingerprint: str
    ) -> dict:
        """Execute one fresh request; cancellation kills only this explicitly owned worker."""
        began = time.monotonic()
        with self.lock:
            if self.timer:
                self.timer.cancel()
            self.active = True
            source = None
            try:
                if cancelled is not None and cancelled.is_set():
                    raise SireError(
                        "resident_cancelled", "Owned worker request cancelled.", 409
                    )
                self._start(fingerprint)
                REQUESTS.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=REQUESTS,
                    suffix=".json",
                    delete=False,
                ) as stream:
                    source = Path(stream.name)
                    json.dump(payload, stream)
                identifier = uuid.uuid4().hex
                message = (
                    json.dumps({"id": identifier, "request_file": str(source)}) + "\n"
                )
                if len(message.encode("utf-8")) > 4096:
                    raise SireError(
                        "resident_limits", "IPC descriptor exceeds its safe bound.", 413
                    )
                self.process.stdin.write(message)
                self.process.stdin.flush()
                while True:
                    if cancelled is not None and cancelled.is_set():
                        raise SireError(
                            "resident_cancelled", "Owned worker request cancelled.", 409
                        )
                    if time.monotonic() - began > timeout:
                        raise SireError(
                            "resident_timeout",
                            "Owned worker exceeded its request budget.",
                            503,
                        )
                    try:
                        value = self.responses.get(timeout=0.05)
                    except queue.Empty:
                        continue
                    if value.get("ipc_error") or value.get("id") != identifier:
                        raise SireError(
                            "resident_failed",
                            "Owned worker failed; no result substituted.",
                            503,
                        )
                    self.requests += 1
                    result = value["result"]
                    result["worker_lifecycle"] = {
                        "process_id": result.get("resources", {}).get(
                            "process_id", self.process.pid
                        ),
                        "launcher_process_id": self.process.pid,
                        "request_number": self.requests,
                        "process_reused": self.requests > 1,
                        "idle_limit_seconds": self.idle_seconds,
                        "execution": "fresh request in bounded owned CPU worker",
                    }
                    return result
            except (OSError, BrokenPipeError) as exc:
                self.close()
                raise SireError(
                    "resident_failed", "Owned worker connection failed.", 503
                ) from exc
            except BaseException:
                self.close()
                raise
            finally:
                if source:
                    source.unlink(missing_ok=True)
                self.active = False
                self.last_used = time.monotonic()
                if self.process:
                    self.timer = threading.Timer(self.idle_seconds, self._idle_close)
                    self.timer.daemon = True
                    self.timer.start()

    def _idle_close(self) -> None:
        with self.lock:
            if (
                not self.active
                and time.monotonic() - self.last_used >= self.idle_seconds
            ):
                self.close()

    def close(self) -> None:
        """Stop this owned child only, draining readers and releasing its model memory."""
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            process, self.process = self.process, None
            if process:
                if not self.active and process.stdin and process.poll() is None:
                    # Idle workers already exit on pipe EOF, including on Windows.
                    try:
                        process.stdin.close()
                        process.wait(timeout=0.25)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                terminate_owned(process)
                for stream in [process.stdin, process.stdout]:
                    if stream:
                        stream.close()
            self.fingerprint = None

    def snapshot(self) -> dict:
        """Expose observed lifecycle only; memory/utilization are not estimated."""
        process = self.process
        return {
            "module": self.module,
            "process_id": process.pid if process and process.poll() is None else None,
            "active": self.active,
            "requests": self.requests,
            "idle_limit_seconds": self.idle_seconds,
            "hardware": "cpu",
            "memory_bytes": None,
        }


def close_workers() -> None:
    """Evict all registered owned CPU workers on application/process shutdown."""
    for worker in list(_WORKERS):
        worker.close()


def snapshots() -> list[dict]:
    """Describe bounded CPU workers without loading models."""
    return [worker.snapshot() for worker in list(_WORKERS)]


atexit.register(close_workers)
