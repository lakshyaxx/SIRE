"""Dedicated guarded-process acceptance of actual local text, media, embeddings and native inference."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.v45_offline_acceptance import GUARD


def main() -> None:
    """Deny external Python network access before imports and inherited worker startup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / ".runtime"):
        raise SystemExit("Private disposable output required")
    out.mkdir(exist_ok=False)
    guard = out / "guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(GUARD, encoding="utf-8")
    os.environ.update(
        SIRE_STATE_DIR=str(out / "db"),
        PYTHONPATH=os.pathsep.join([str(guard), str(ROOT)]),
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    exec(compile(GUARD, str(guard / "sitecustomize.py"), "exec"), {})
    from app.media.runtime import run
    from app.voice.service import transcribe_bytes
    from app.knowledge.embeddings import embed
    from app.prediction.hub import predict
    from app.prediction.telemetry import asset_history
    from app.prediction.policy import default_model
    from app.core.worker_pool import close_workers
    import httpx

    proof = {
        "scope": "External Python sockets/DNS denied in this process and inherited Python workers; local Ollama allowed. No OS-wide air-gap or already-running Ollama egress guarantee.",
        "checks": [],
    }

    def record(name, operation):
        began = time.perf_counter()
        try:
            row = {"name": name, "status": "passed", "result": operation()}
        except Exception as exc:
            row = {
                "name": name,
                "status": "failed",
                "error": type(exc).__name__ + ": " + str(exc),
            }
        row["seconds"] = time.perf_counter() - began
        proof["checks"].append(row)
        (out / "results.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
        print(
            json.dumps({k: row[k] for k in ["name", "status", "seconds"]}), flush=True
        )

    def denied():
        try:
            socket.getaddrinfo("example.invalid", 443)
        except OSError:
            return {"external_dns": "denied"}
        raise AssertionError("External DNS was not blocked")

    def text():
        response = httpx.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "qwen3:4b-instruct",
                "prompt": "Say hello briefly.",
                "stream": False,
                "keep_alive": 120,
                "options": {
                    "num_predict": 12,
                    "num_ctx": 4096,
                    "seed": 42,
                    "temperature": 0,
                },
            },
            timeout=150,
            trust_env=False,
        )
        response.raise_for_status()
        result = response.json()
        assert result.get("response")
        return result

    def semantic():
        result = embed(["A bearing supports rotating machinery."])
        vectors = result.pop("vectors")
        assert len(vectors) == 1 and len(vectors[0]) == 384
        return result

    def speech():
        result = run("tts", {"text": "Hello.", "voice_id": 0, "speed": 1})
        raw = result.pop("audio_bytes")
        assert raw[:4] == b"RIFF" and result["frames"] > 0
        (out / "actual_offline.wav").write_bytes(raw)
        result["sha256"] = hashlib.sha256(raw).hexdigest()
        return result

    def asr():
        content = (out / "actual_offline.wav").read_bytes()
        result = transcribe_bytes(content)
        assert result["text"]
        return result

    def outage():
        try:
            httpx.get("http://127.0.0.1:11439/api/tags", timeout=3, trust_env=False)
        except httpx.ConnectError:
            return {"actual_loopback_connection": "refused"}
        raise AssertionError("Expected nonexistent local service was reachable")

    try:
        record("external_dns_denied", denied)
        record("actual_local_qwen", text)
        record("actual_local_embeddings", semantic)
        record("actual_local_speech", speech)
        record("actual_local_asr", asr)
        record(
            "actual_saved_native",
            lambda: predict(
                default_model("FD001")["model_id"],
                "FD001",
                asset_history("FD001-ENGINE-001", "FD001"),
            ),
        )
        record("actual_refused_loopback", outage)
    finally:
        close_workers()
    if any(row["status"] == "failed" for row in proof["checks"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
