"""Isolated-process offline/failure acceptance; never disables the user's OS networking."""

import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / ".runtime/v45/offline_acceptance"
GUARD = """import ipaddress,socket
def local(host):
    if isinstance(host,bytes): host=host.decode()
    if host == "localhost": return True
    try: return ipaddress.ip_address(host).is_loopback
    except ValueError: return False
_connect=socket.socket.connect
_connect_ex=socket.socket.connect_ex
_resolve=socket.getaddrinfo
def connect(self,address):
    if isinstance(address,tuple) and not local(address[0]): raise OSError("V45 test: external networking denied")
    return _connect(self,address)
def connect_ex(self,address):
    if isinstance(address,tuple) and not local(address[0]): raise OSError("V45 test: external networking denied")
    return _connect_ex(self,address)
def resolve(host,*args,**kwargs):
    if host is not None and not local(host): raise OSError("V45 test: external DNS denied")
    return _resolve(host,*args,**kwargs)
socket.socket.connect=connect
socket.socket.connect_ex=connect_ex
socket.getaddrinfo=resolve
"""


def main() -> None:
    """Run actual local essentials and a refused provider without substituting an answer."""
    OUTPUT.mkdir(parents=True, exist_ok=False)
    guard = OUTPUT / "guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(GUARD, encoding="utf-8")
    os.environ.update(
        SIRE_STATE_DIR=str(OUTPUT / "db"),
        SIRE_WEB_BUILD="dist-v3",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join((str(guard), str(ROOT))),
    )
    exec(compile(GUARD, str(guard / "sitecustomize.py"), "exec"), {})
    from fastapi.testclient import TestClient
    from app.api.main import create_app
    from app.core.config import SETTINGS
    from app.prediction.policy import default_model

    results = {
        "scope": "External DNS/connect denied in this dedicated Python process and Python children through inherited sitecustomize. Actual loopback Ollama remains allowed. OS-wide network disconnection and existing provider-service egress are not controlled or claimed.",
        "checks": [],
    }

    def save() -> None:
        (OUTPUT / "results.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )

    def record(name, operation) -> None:
        began = time.monotonic()
        try:
            value = {"name": name, "status": "pass", "evidence": operation()}
        except Exception as exc:
            value = {
                "name": name,
                "status": "fail",
                "error": f"{type(exc).__name__}: {exc}",
            }
        value["elapsed_seconds"] = time.monotonic() - began
        results["checks"].append(value)
        save()
        print(
            json.dumps(
                {key: value[key] for key in ("name", "status", "elapsed_seconds")}
            ),
            flush=True,
        )

    with TestClient(create_app(state_dir=OUTPUT / "db", probe_model=False)) as client:
        cid = client.post(
            "/api/v1/conversations", json={"title": "V45 disposable offline"}
        ).json()["id"]

        def turn(content, ids=None):
            response = client.post(
                "/api/v1/chat/message",
                json={
                    "conversation_id": cid,
                    "content": content,
                    "attachment_ids": ids or [],
                },
            )
            response.raise_for_status()
            return [
                json.loads(line[6:])
                for line in response.text.splitlines()
                if line.startswith("data: ")
            ]

        def deny_external():
            import socket

            try:
                socket.getaddrinfo("example.com", 443)
            except OSError as exc:
                assert "external DNS denied" in str(exc)
                return {"denied_before_DNS": str(exc)}
            raise AssertionError("External DNS was not denied")

        record("external_DNS_guard", deny_external)

        def local_text():
            events = turn(
                "Briefly explain what a rolling bearing does in two sentences."
            )
            assert events[-1]["status"] == "complete", events[-1]
            assert any(event.get("text", "").strip() for event in events)
            return events

        record("real_local_text_with_external_guard", local_text)

        def prediction():
            model = default_model("FD001")
            response = client.post(
                "/api/v1/predictions/run",
                json={
                    "dataset": "FD001",
                    "model_id": model["model_id"],
                    "asset_id": "FD001-ENGINE-001",
                },
            )
            response.raise_for_status()
            assert response.json()["rul_cycles"] is not None
            return response.json()

        record("genuine_native_child_with_external_guard", prediction)

        def unavailable():
            original = SETTINGS["ollama_base_url"]
            try:
                SETTINGS["ollama_base_url"] = "http://127.0.0.1:1"
                events = turn("Explain rolling bearings in detail.")
                assert events[-1]["status"] == "error", events[-1]
                assert not any(event["type"] == "delta" for event in events), events
                return events
            finally:
                SETTINGS["ollama_base_url"] = original

        record("real_connection_refused_no_fabricated_answer", unavailable)

        def deterministic_source():
            response = client.post(
                "/api/v1/attachments",
                data={"conversation_id": cid},
                files={
                    "file": (
                        "offline-source.txt",
                        b"Explicit test fixture: inspections require traceable source records.",
                    )
                },
            )
            response.raise_for_status()
            original = SETTINGS["ollama_base_url"]
            try:
                SETTINGS["ollama_base_url"] = "http://127.0.0.1:1"
                events = turn(
                    "According to this document, quote the actual record passages with source locators.",
                    [response.json()["id"]],
                )
                assert events[-1]["status"] == "complete", events[-1]
                assert events[-1]["metadata"]["model_activity"] == []
                return events
            finally:
                SETTINGS["ollama_base_url"] = original

        record("actual_document_works_with_provider_unavailable", deterministic_source)
    save()


if __name__ == "__main__":
    main()
