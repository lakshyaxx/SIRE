"""Verified local MiniLM inference in an owned, cancellable CPU worker."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Event
import time
import yaml
from app.core.config import ROOT
from app.core.errors import SireError
from app.providers.resources import SCHEDULER
from app.core.worker_pool import WorkerProcess, terminate_owned

POLICY = yaml.safe_load((ROOT / "config/retrieval.yaml").read_text(encoding="utf-8"))
EMBEDDING_WORKER = WorkerProcess(
    "app.knowledge.embedding_worker",
    POLICY.get("resident_idle_seconds", 90),
    POLICY["threads"],
)


def model_files(verify: bool = True) -> dict[str, Path]:
    """Resolve only pinned local files; never contact a model hub during inference."""
    result = {name: ROOT / POLICY["model_root"] / name for name in POLICY["files"]}
    for name, path in result.items():
        if not path.is_file():
            raise SireError(
                "embedding_unavailable",
                "Install the documented optional local semantic model.",
                503,
            )
        if verify:
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != POLICY["files"][name]:
                raise SireError(
                    "embedding_integrity",
                    "Semantic model integrity mismatch; inference refused.",
                    503,
                )
    return result


def fingerprint() -> str:
    """Version vectors by weights, tokenizer, pooling and inference implementation."""
    return hashlib.sha256(
        json.dumps(
            [
                POLICY["files"],
                POLICY["max_tokens"],
                (ROOT / "app/knowledge/embedding_worker.py").read_text(
                    encoding="utf-8"
                ),
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()


def readiness() -> dict:
    """Inspect configured local files/packages without loading neural libraries."""
    try:
        model_files(False)
        ready = all(
            (ROOT / POLICY["dependencies"] / name).is_dir()
            for name in ["onnxruntime", "tokenizers"]
        )
    except SireError:
        ready = False
    return {
        "configured": ready,
        "model": POLICY["model_id"],
        "revision": POLICY["revision"],
        "license": POLICY["license"],
        "runtime": "ONNX Runtime CPU",
        "dimensions": POLICY["dimensions"],
        "quantization": "uint8",
        "network": "No inference downloads or hosted calls",
        "health": (
            "Pinned files configured; each execution verifies hashes"
            if ready
            else "Local model/runtime not configured"
        ),
    }


def _one_shot_embed(texts: list[str], cancelled: Event | None = None) -> dict:
    """Run actual embeddings under the existing heavy-operation lease and bounded IPC."""
    if (
        not texts
        or len(texts) > POLICY["max_index_chunks"] + 1
        or any(len(t) > 8000 for t in texts)
    ):
        raise SireError(
            "embedding_limits", "Embedding input exceeds the configured limits.", 413
        )
    model_files()
    if not readiness()["configured"]:
        raise SireError(
            "embedding_unavailable", "Local semantic runtime unavailable.", 503
        )
    stop = cancelled or Event()
    began = time.perf_counter()
    process = None
    with SCHEDULER.lease(
        "embedding", cancelled=stop, model=POLICY["model_id"]
    ) as lease:
        try:
            # A file avoids blocking pipe writes before the cancellation loop on Windows.
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as request:
                json.dump({"texts": texts}, request)
                request.seek(0)
                process = subprocess.Popen(
                    [sys.executable, "-m", "app.knowledge.embedding_worker"],
                    cwd=ROOT,
                    stdin=request,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    env=dict(
                        os.environ,
                        HF_HUB_OFFLINE="1",
                        TRANSFORMERS_OFFLINE="1",
                        CUDA_VISIBLE_DEVICES="",
                        PYTHONDONTWRITEBYTECODE="1",
                        OMP_NUM_THREADS=str(POLICY["threads"]),
                    ),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                while True:
                    if stop.is_set():
                        raise SireError(
                            "embedding_cancelled", "Semantic inference cancelled.", 409
                        )
                    if time.perf_counter() - began > POLICY["timeout_seconds"]:
                        raise SireError(
                            "embedding_timeout",
                            "Semantic inference exceeded its budget.",
                            503,
                        )
                    try:
                        stdout, stderr = process.communicate(timeout=0.1)
                        break
                    except subprocess.TimeoutExpired:
                        continue
            if process.returncode:
                raise SireError(
                    "embedding_failed",
                    "Local semantic worker failed; no vectors substituted.",
                    503,
                )
            result = json.loads(stdout)
            if len(result["vectors"]) != len(texts) or any(
                len(v) != POLICY["dimensions"] for v in result["vectors"]
            ):
                raise SireError(
                    "embedding_output", "Invalid local vector dimensions.", 503
                )
            result["elapsed_seconds"] = time.perf_counter() - began
            lease["provider_metrics"] = {
                k: v for k, v in result.items() if k != "vectors"
            }
            return result
        finally:
            if process and process.poll() is None:
                terminate_owned(process)
                process.communicate(timeout=5)


def embed(texts: list[str], cancelled: Event | None = None) -> dict:
    """Reuse one owned CPU session for fresh queries under the existing scheduler."""
    if not POLICY.get("resident_workers", False):
        return _one_shot_embed(texts, cancelled)
    if (
        not texts
        or len(texts) > POLICY["max_index_chunks"] + 1
        or any(len(t) > 8000 for t in texts)
    ):
        raise SireError(
            "embedding_limits", "Embedding input exceeds configured limits.", 413
        )
    model_files()
    if not readiness()["configured"]:
        raise SireError(
            "embedding_unavailable", "Local semantic runtime unavailable.", 503
        )
    stop = cancelled or Event()
    began = time.perf_counter()
    try:
        with SCHEDULER.lease(
            "embedding", cancelled=stop, model=POLICY["model_id"]
        ) as lease:
            result = EMBEDDING_WORKER.execute(
                {"texts": texts}, stop, POLICY["timeout_seconds"], fingerprint()
            )
            if len(result["vectors"]) != len(texts) or any(
                len(v) != POLICY["dimensions"] for v in result["vectors"]
            ):
                raise SireError(
                    "embedding_output", "Invalid local vector dimensions.", 503
                )
            result["elapsed_seconds"] = time.perf_counter() - began
            lease["provider_metrics"] = {
                k: v for k, v in result.items() if k != "vectors"
            }
            return result
    except SireError as exc:
        if (
            exc.code == "resident_failed"
            and POLICY.get("resident_fallback", True)
            and not stop.is_set()
        ):
            result = _one_shot_embed(texts, stop)
            result["worker_fallback"] = {
                "from": "resident",
                "to": "original_one_shot",
                "reason": exc.code,
            }
            return result
        if exc.code in {"resident_cancelled", "resident_timeout"}:
            raise SireError(
                (
                    "embedding_cancelled"
                    if exc.code == "resident_cancelled"
                    else "embedding_timeout"
                ),
                exc.message,
                exc.status,
            ) from exc
        raise
