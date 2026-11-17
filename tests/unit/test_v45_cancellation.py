"""Cancellation of real async transport and owned worker processes; no inference results are fabricated."""

import asyncio
import threading
import subprocess
import sys
import pytest
import httpx
from app.providers import ollama
from app.providers.resources import ResourceScheduler
from app.investigation.schemas import Proposal
from app.prediction import hub, telemetry
from app.core.errors import SireError


def test_stop_cancels_structured_http_and_releases_provider_lease(
    tmp_path, monkeypatch
):
    scheduler = ResourceScheduler(tmp_path / "test-only-model.lock")
    monkeypatch.setattr(ollama, "SCHEDULER", scheduler)
    monkeypatch.setattr(ollama, "readiness", lambda: {"models": ["test-only-model"]})
    original = httpx.AsyncClient

    async def run():
        entered = asyncio.Event()
        closed = asyncio.Event()
        stop = asyncio.Event()

        async def blocked(request):
            entered.set()
            try:
                await asyncio.Future()
            finally:
                closed.set()

        monkeypatch.setattr(
            ollama.httpx,
            "AsyncClient",
            lambda **kwargs: original(transport=httpx.MockTransport(blocked), **kwargs),
        )
        task = asyncio.create_task(
            ollama.generate_async([], Proposal, "test-only-model", stop)
        )
        await entered.wait()
        stop.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (
            closed.is_set()
            and not scheduler.snapshot()["active"]
            and not scheduler.snapshot()["waiting"]
        )
        assert ollama.PROVIDER_LOCK.acquire(blocking=False)
        ollama.PROVIDER_LOCK.release()

    asyncio.run(run())


def test_native_cancel_terminates_only_owned_test_worker(tmp_path, monkeypatch):
    scheduler = ResourceScheduler(tmp_path / "test-only-native.lock")
    monkeypatch.setattr(hub, "SCHEDULER", scheduler)
    original = subprocess.Popen
    started = threading.Event()
    children = []
    errors = []
    stop = threading.Event()

    def delayed_worker(*args, **kwargs):
        child = original(
            [sys.executable, "-c", "import time; time.sleep(10)"], **kwargs
        )
        children.append(child)
        started.set()
        return child

    monkeypatch.setattr(hub.subprocess, "Popen", delayed_worker)
    model = next(
        row for row in hub.catalog() if row["dataset"] == "FD001" and row["default"]
    )
    frame = telemetry.asset_history("FD001-ENGINE-001", "FD001")

    def work():
        try:
            hub.predict(model["model_id"], "FD001", frame, cancel_event=stop)
        except SireError as exc:
            errors.append(exc.code)

    task = threading.Thread(target=work)
    task.start()
    assert started.wait(3)
    stop.set()
    task.join(timeout=3)
    assert not task.is_alive() and errors == ["inference_cancelled"]
    assert len(children) == 1 and children[0].poll() is not None
    assert not scheduler.snapshot()["active"]
    assert hub.INFERENCE_LOCK.acquire(blocking=False)
    hub.INFERENCE_LOCK.release()
