"""Real owned-process IPC regression controls; these are not model benchmarks."""

import json
import os
from pathlib import Path
import sys
import threading
import time
import pytest
from app.core.worker_pool import WorkerProcess, request_file
from app.core.errors import SireError


@pytest.fixture
def worker(tmp_path: Path):
    """Use a controlled real child to exercise lifecycle independently of neural models."""
    script = tmp_path / "test_ipc.py"
    script.write_text(
        """import json,sys,time,pathlib,os
sys.path.insert(0,str(pathlib.Path.cwd()))
from app.core.worker_pool import serve
def execute(p):
 if p.get('bad'):
  print('TEST-ONLY INVALID PROTOCOL',flush=True); os._exit(1)
 time.sleep(p.get('wait',0))
 return {'actual_input':p.get('value'),'actual_process_id':os.getpid()}
serve(execute)
""",
        encoding="utf-8",
    )
    owned = WorkerProcess("test-only", 1, command=[sys.executable, str(script)])
    yield owned
    owned.close()


def test_reuse_fingerprint_and_no_previous_result_substitution(worker):
    first = worker.execute({"value": "TEST-ONLY first"}, None, 5, "version1")
    process = worker.process
    second = worker.execute({"value": "TEST-ONLY second"}, None, 5, "version1")
    assert first["actual_input"] != second["actual_input"]
    assert (
        first["worker_lifecycle"]["process_id"]
        == second["worker_lifecycle"]["process_id"]
    )
    assert second["worker_lifecycle"]["process_reused"]
    third = worker.execute({"value": "TEST-ONLY third"}, None, 5, "version2")
    assert process.poll() is not None
    assert not third["worker_lifecycle"]["process_reused"]


def test_active_cancel_terminates_only_owned_process_and_recovers(worker):
    initial = worker.execute({"value": "TEST-ONLY identity"}, None, 5, "version1")
    actual_handle = None
    if os.name == "nt":
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        actual_handle = kernel.OpenProcess(
            0x100000, False, initial["actual_process_id"]
        )
        assert actual_handle
    stop = threading.Event()
    errors = []

    def execute():
        try:
            worker.execute({"wait": 10}, stop, 20, "version1")
        except SireError as exc:
            errors.append(exc.code)

    thread = threading.Thread(target=execute)
    thread.start()
    deadline = time.monotonic() + 5
    while worker.process is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert worker.process is not None
    process = worker.process
    stop.set()
    thread.join(5)
    assert not thread.is_alive() and errors == ["resident_cancelled"]
    assert process.poll() is not None
    if actual_handle:
        try:
            assert kernel.WaitForSingleObject(actual_handle, 2000) == 0
        finally:
            kernel.CloseHandle(actual_handle)
    assert (
        worker.execute({"value": "TEST-ONLY recovery"}, None, 5, "version1")[
            "actual_input"
        ]
        == "TEST-ONLY recovery"
    )


def test_timeout_protocol_failure_and_idle_eviction(worker):
    with pytest.raises(SireError) as timeout:
        worker.execute({"wait": 10}, None, 0.1, "version1")
    assert timeout.value.code == "resident_timeout" and worker.process is None
    with pytest.raises(SireError) as protocol:
        worker.execute({"bad": True}, None, 5, "version1")
    assert protocol.value.code == "resident_failed" and worker.process is None
    worker.execute({"value": "TEST-ONLY idle"}, None, 5, "version1")
    process = worker.process
    deadline = time.monotonic() + 3
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    assert process.poll() is not None


def test_request_file_scope_guard(tmp_path: Path):
    path = tmp_path / "outside.json"
    path.write_text(json.dumps({"test": "untrusted"}))
    with pytest.raises(ValueError):
        request_file(str(path))


def test_parent_pipe_closure_stops_a_busy_owned_worker(worker):
    worker.execute({"value": "TEST-ONLY ready"}, None, 5, "version1")
    errors = []

    def execute():
        try:
            worker.execute({"wait": 10}, None, 20, "version1")
        except SireError as exc:
            errors.append(exc.code)

    thread = threading.Thread(target=execute)
    thread.start()
    time.sleep(0.1)
    worker.process.stdin.close()
    thread.join(5)
    assert not thread.is_alive() and errors == ["resident_failed"]


def test_cached_wav_never_claims_a_current_worker_execution(monkeypatch):
    from app.media import runtime
    from app.media.cache import SpeechCache

    cache = SpeechCache(1, 100, 10)
    cache.put(
        runtime._speech_key("TEST-ONLY"),
        {
            "audio_bytes": b"TEST-ONLY",
            "resources": {"cpu_seconds": 1},
            "worker_lifecycle": {"execution": "fresh request"},
            "model_reused": True,
        },
    )
    monkeypatch.setattr(runtime, "SPEECH_CACHE", cache)
    monkeypatch.setattr(runtime, "model_files", lambda *args, **kwargs: {})
    result = runtime.run("tts", {"text": "TEST-ONLY"})
    assert result["cache"]["hit"]
    assert result["resources"]["worker_started"] is False
    assert result["worker_lifecycle"]["worker_started"] is False
    assert result["model_reused"] is False
