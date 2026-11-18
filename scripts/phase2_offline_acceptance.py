"""Dedicated guarded-process offline checks with real local models and no OS network changes."""

import argparse
import json
import os
from pathlib import Path
import socket
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.v45_offline_acceptance import GUARD


def main() -> None:
    """Deny external Python DNS/connect, then run actual model, native and retrieval calls."""
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
        SIRE_WEB_BUILD="dist",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join([str(guard), str(ROOT)]),
    )
    exec(compile(GUARD, str(guard / "sitecustomize.py"), "exec"), {})
    from fastapi.testclient import TestClient
    from app.api.main import create_app
    from app.core.config import SETTINGS
    from app.prediction.policy import default_model

    proof = {
        "scope": "External Python DNS/connect denied in this dedicated process and inherited Python children. Actual loopback Ollama allowed. OS air-gap and already-running Ollama egress not controlled or claimed.",
        "checks": [],
    }

    def save():
        (out / "results.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")

    def record(name, operation):
        began = time.perf_counter()
        try:
            row = {"name": name, "status": "passed", "result": operation()}
        except Exception as exc:
            row = {
                "name": name,
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }
        row["seconds"] = time.perf_counter() - began
        proof["checks"].append(row)
        save()
        print(
            json.dumps({k: row[k] for k in ["name", "status", "seconds"]}), flush=True
        )

    with TestClient(create_app(state_dir=out / "db", probe_model=False)) as c:
        cid = c.post("/api/v1/conversations", json={}).json()["id"]

        def denied():
            try:
                socket.getaddrinfo("example.com", 443)
            except OSError:
                return {"external_dns": "denied"}
            raise AssertionError("External DNS was not denied")

        record("external_dns_denied", denied)

        def text():
            r = c.post(
                "/api/v1/chat/message",
                json={
                    "conversation_id": cid,
                    "content": "In two sentences explain how rolling bearings reduce friction.",
                },
            )
            r.raise_for_status()
            events = [
                json.loads(s[6:]) for s in r.text.splitlines() if s.startswith("data: ")
            ]
            assert events[-1]["status"] == "complete"
            return events

        record("actual_local_qwen", text)

        def semantics():
            r = c.post(
                "/api/v1/attachments",
                data={"conversation_id": cid},
                files={
                    "file": (
                        "TEST-ONLY.txt",
                        b"TEST-ONLY: An inverter regulates rotational velocity of an electric motor.",
                    )
                },
            )
            r.raise_for_status()
            r = c.post(
                "/api/v1/specialists/execute",
                json={
                    "conversation_id": cid,
                    "request_id": uuid.uuid4().hex,
                    "tool_id": "knowledge.retrieve",
                    "arguments": {
                        "text": "variable frequency drive",
                        "mode": "semantic",
                    },
                },
            )
            r.raise_for_status()
            v = r.json()
            assert v["output"]["passages"]
            return v

        record("actual_offline_semantic_worker", semantics)

        def native():
            model = default_model("FD001")
            r = c.post(
                "/api/v1/predictions/run",
                json={
                    "dataset": "FD001",
                    "model_id": model["model_id"],
                    "asset_id": "FD001-ENGINE-001",
                },
            )
            r.raise_for_status()
            assert r.json()["rul_cycles"] is not None
            return r.json()

        record("actual_saved_native_worker", native)

        def refused():
            original = SETTINGS["ollama_base_url"]
            try:
                SETTINGS["ollama_base_url"] = "http://127.0.0.1:1"
                r = c.post(
                    "/api/v1/chat/message",
                    json={
                        "conversation_id": cid,
                        "content": "Explain rolling bearing wear in two sentences.",
                    },
                )
                r.raise_for_status()
                events = [
                    json.loads(s[6:])
                    for s in r.text.splitlines()
                    if s.startswith("data: ")
                ]
                assert events[-1]["status"] == "error" and not any(
                    e["type"] == "delta" for e in events
                )
                return events
            finally:
                SETTINGS["ollama_base_url"] = original

        record("real_refused_provider_no_substitute", refused)
    if any(r["status"] == "failed" for r in proof["checks"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
