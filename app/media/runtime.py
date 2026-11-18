"""Isolated local speech/video jobs with fixed resources, integrity checks and cancellation."""

import hashlib
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import yaml
from app.core.config import ROOT
from app.core.errors import SireError
from app.prediction.hub import INFERENCE_LOCK
from app.providers.ollama import PROVIDER_LOCK
from app.providers.resources import SCHEDULER
from app.media.cache import SpeechCache

POLICY = yaml.safe_load((ROOT / "config/media.yaml").read_text(encoding="utf-8"))
DEPENDENCIES = ROOT / POLICY["optional_dependencies"]
MODELS = Path(os.environ.get("SIRE_MEDIA_MODELS", str(ROOT / POLICY["model_root"])))
JOBS: dict[str, threading.Event] = {}
JOB_LOCK = threading.Lock()
SPEECH_CACHE = SpeechCache(
    POLICY["tts_cache_entries"],
    POLICY["tts_cache_bytes"],
    POLICY["tts_cache_ttl_seconds"],
)


def _speech_key(text: str, voice_id: int = 0, speed: float = 1) -> str:
    """Bind cached actual WAV to exact input, pinned weights and synthesis/normalizer code."""
    data = {
        "text": text,
        "models": POLICY["models"]["tts"],
        "threads": POLICY["tts_threads"],
        "voice_id": voice_id,
        "speed": float(speed),
    }
    for name in ["app/media/worker.py", "app/voice/text.py"]:
        data[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def model_files(kind: str, verify: bool = True) -> dict[str, Path]:
    """Resolve only configured model filenames and optionally verify every pinned byte hash."""
    spec = POLICY["models"][kind]
    paths = {name: MODELS / spec["directory"] / name for name in spec["files"]}
    for name, path in paths.items():
        if not path.is_file():
            raise SireError(
                "media_model_missing",
                "Run scripts/setup_media.py to provision verified optional local models.",
                503,
            )
        if verify:
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != spec["files"][name]:
                raise SireError(
                    "media_model_integrity",
                    "Optional model hash mismatch; operation refused.",
                    503,
                )
    return paths


def readiness() -> dict:
    """Read configured/probed local readiness without loading models or accessing microphones."""
    result = {
        "asr_ready": False,
        "tts_ready": False,
        "video_ready": False,
        "asr_configured": False,
        "tts_configured": False,
        "network": "Local workers only; no hosted speech or browser cloud recognition.",
        "hardware_interaction": "Browser microphone permission and speaker playback require user interaction; not probed here.",
    }
    proof_path = MODELS / "verified.json"
    proof = (
        json.loads(proof_path.read_text(encoding="utf-8"))
        if proof_path.is_file()
        else {}
    )
    for kind in ["asr", "tts"]:
        present = (DEPENDENCIES / "sherpa_onnx").is_dir()
        try:
            profile = (
                POLICY.get("asr_default_profile", "asr") if kind == "asr" else kind
            )
            model_files(profile, verify=False)
            result[kind + "_configured"] = present
            expected = hashlib.sha256(
                json.dumps(POLICY["models"][profile]["files"], sort_keys=True).encode()
            ).hexdigest()
            result[kind + "_ready"] = (
                present and proof.get(profile, {}).get("model_fingerprint") == expected
            )
        except SireError:
            continue
    result["video_ready"] = (DEPENDENCIES / "cv2").is_dir() and bool(
        proof.get("video", {}).get("decoded_test")
    )
    result["vad_configured"] = False
    result["vad_ready"] = False
    try:
        model_files("vad", verify=False)
        result["vad_configured"] = (DEPENDENCIES / "sherpa_onnx").is_dir()
        vad_proof = MODELS / "silero-vad/verified.json"
        if vad_proof.is_file():
            from app.evidence.ledger import digest

            result["vad_ready"] = result["vad_configured"] and json.loads(
                vad_proof.read_text(encoding="utf-8")
            ).get("model_fingerprint") == digest(POLICY["models"]["vad"]["files"])
    except SireError:
        result["vad_configured"] = False
    result["reason"] = (
        "Readiness reflects configured files and successful worker probes; microphone/speaker interaction is separate."
    )
    return result


def cancel(identifier: str) -> bool:
    """Signal only an active known local media job."""
    with JOB_LOCK:
        event = JOBS.get(identifier)
    if event:
        event.set()
        return True
    return False


def run(
    operation: str,
    payload: dict,
    identifier: str | None = None,
    cancel_event: threading.Event | None = None,
) -> dict:
    """Run one bounded subprocess and free its model memory afterward; no startup downloads."""
    started = time.monotonic()
    if operation not in {"asr", "tts", "video"}:
        raise ValueError("Unsupported media operation")
    package = "cv2" if operation == "video" else "sherpa_onnx"
    if not (DEPENDENCIES / package).is_dir():
        raise SireError(
            "media_runtime_missing",
            "Optional local runtime is missing. Run scripts/setup_media.py.",
            503,
        )
    if operation != "video":
        profile = (
            payload.get("profile", POLICY.get("asr_default_profile", "asr"))
            if operation == "asr"
            else operation
        )
        if operation == "asr" and profile not in {"asr", "asr_base"}:
            raise SireError("asr_profile", "Unsupported local ASR profile.", 422)
        model_files(profile)
    event = cancel_event if cancel_event is not None else threading.Event()
    if event.is_set():
        raise SireError(
            "media_cancelled", "Media operation cancelled before inference.", 409
        )
    if identifier:
        with JOB_LOCK:
            if identifier in JOBS:
                raise SireError(
                    "media_job_active", "This media request is already active.", 409
                )
            JOBS[identifier] = event
    acquired = []
    scheduler_stack = ExitStack()
    process = None
    temporary_directory = None
    cache_key = None
    try:
        cache_key = (
            _speech_key(
                payload["text"], payload.get("voice_id", 0), payload.get("speed", 1)
            )
            if operation == "tts"
            else None
        )
        if cache_key:
            cached = SPEECH_CACHE.get(cache_key)
            if cached is not None:
                cached["cache"] = {
                    "hit": True,
                    "scope": "Reused actual prior local WAV; no model executed for this request",
                }
                cached["elapsed_seconds"] = time.monotonic() - started
                cached["phase_timings"] = {
                    "cache_request_seconds": cached["elapsed_seconds"]
                }
                cached["original_synthesis_resources"] = cached.pop("resources", {})
                cached["resources"] = {
                    "worker_started": False,
                    "scope": "Cached request; original synthesis worker counters are retained separately.",
                }
                return cached
        grant = scheduler_stack.enter_context(
            SCHEDULER.lease(
                operation,
                cancelled=event,
                priority=0 if operation in {"asr", "tts"} else 5,
            )
        )
        for lock in [INFERENCE_LOCK, PROVIDER_LOCK]:
            if not lock.acquire(blocking=False):
                raise SireError(
                    "media_busy",
                    "Another local model is active; retry after it finishes.",
                    429,
                )
            acquired.append(lock)
        directory = ROOT / ".runtime/media_jobs"
        directory.mkdir(parents=True, exist_ok=True)
        temporary_directory = tempfile.TemporaryDirectory(prefix="job_", dir=directory)
        name = temporary_directory.name
        workspace = Path(name).resolve()
        if not workspace.is_relative_to(directory.resolve()):
            raise ValueError("Media job left its private workspace")
        request = {
            "operation": operation,
            "payload": payload,
            "workspace": str(workspace),
        }
        process = subprocess.Popen(
            [sys.executable, "-m", "app.media.worker"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=dict(
                os.environ,
                PYTHONDONTWRITEBYTECODE="1",
                OMP_NUM_THREADS=str(
                    POLICY["tts_threads"] if operation == "tts" else POLICY["threads"]
                ),
                OPENBLAS_NUM_THREADS=str(
                    POLICY["tts_threads"] if operation == "tts" else POLICY["threads"]
                ),
                CUDA_VISIBLE_DEVICES="",
            ),
        )
        first = True
        while True:
            if event.is_set():
                raise SireError(
                    "media_cancelled",
                    "Media operation cancelled; no transcript or audio substituted.",
                    409,
                )
            if time.monotonic() - started > POLICY["timeout_seconds"]:
                raise SireError(
                    "media_timeout", "Local media worker reached its time limit.", 503
                )
            try:
                stdout, stderr = process.communicate(
                    json.dumps(request) if first else None, timeout=0.25
                )
                break
            except subprocess.TimeoutExpired:
                first = False
        if process.returncode:
            raise SireError(
                "media_processing_failed",
                "The local media worker rejected or could not process this input. No result was substituted.",
                422,
            )
        output = json.loads(stdout)
        if output.get("error"):
            raise SireError(
                output["error"]["code"],
                output["error"]["message"],
                output["error"].get("status", 422),
            )
        if operation == "tts":
            output["audio_bytes"] = (workspace / "speech.wav").read_bytes()
            snapshot = {
                key: value for key, value in output.items() if key != "phase_timings"
            }
            snapshot["original_synthesis_timings"] = output.get("phase_timings", {})
            SPEECH_CACHE.put(cache_key, snapshot)
            output["cache"] = {"hit": False, "scope": "Actual new local synthesis"}
        elif operation == "video":
            for frame in output["frames"]:
                frame["image_bytes"] = (workspace / frame.pop("file")).read_bytes()
        output["resource_scheduling"] = dict(grant)
        output["elapsed_seconds"] = time.monotonic() - started
        return output
    except SireError as exc:
        if exc.code == "resource_cancelled":
            raise SireError(
                "media_cancelled",
                "Media operation cancelled while waiting for a model slot.",
                409,
            ) from exc
        raise
    finally:
        try:
            if process and process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            if temporary_directory is not None:
                temporary_directory.cleanup()
        finally:
            for lock in reversed(acquired):
                lock.release()
            scheduler_stack.close()
            if identifier:
                with JOB_LOCK:
                    JOBS.pop(identifier, None)
