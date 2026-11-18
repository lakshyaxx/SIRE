"""Actual guarded local cancellation, streaming, concurrent work and restart acceptance."""

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Exercise real local requests; retain failures and never synthesize a passing result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=["full", "seed", "recovery"], default="full")
    args = parser.parse_args()
    state, out = args.state_dir.resolve(), args.output.resolve()
    if (
        not state.is_relative_to(ROOT / ".runtime")
        or state == ROOT / ".runtime/v2"
        or not out.is_relative_to(ROOT / ".runtime")
    ):
        raise SystemExit("Disposable namespace required")
    out.mkdir(exist_ok=args.phase != "full")
    profile = json.loads(args.profile.read_text())
    cid = profile["conversation_id"]
    proof = {
        "scope": "Real local reliability controls; latency is descriptive, not a paired speed benchmark.",
        "cases": [],
    }
    with httpx.Client(
        base_url="http://127.0.0.1:8001/api/v1", timeout=180, trust_env=False
    ) as api:
        contract = api.get("/specialists/contracts")
        contract.raise_for_status()
        assert (
            contract.json()["state_namespace"]
            == hashlib.sha256(
                str((state / "sire.sqlite3").resolve()).encode()
            ).hexdigest()
        )

        def save():
            (out / "results.json").write_text(
                json.dumps(proof, indent=2), encoding="utf-8"
            )

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
            proof["cases"].append(row)
            save()
            print(
                json.dumps({k: row[k] for k in ["name", "status", "seconds"]}),
                flush=True,
            )

        def chat(text, rid=None, model=None, conversation_id=None):
            body = {
                "conversation_id": conversation_id or cid,
                "request_id": rid or uuid.uuid4().hex,
                "content": text,
            }
            if model:
                body["model"] = model
            response = api.post("/chat/message", json=body)
            response.raise_for_status()
            return [
                json.loads(line[6:])
                for line in response.text.splitlines()
                if line.startswith("data: ")
            ]

        def active(capability=None, require_gpu=False):
            deadline = time.perf_counter() + 30
            while time.perf_counter() < deadline:
                value = api.get("/runtime/resources", timeout=5).json()
                if any(
                    not capability or row["capability"] == capability
                    for row in value["scheduler"]["active"]
                ) and (
                    not require_gpu
                    or any(
                        m.get("size_vram", 0) > 0
                        for m in value["ollama_residency"].get("models") or []
                    )
                ):
                    return value
                time.sleep(0.05)
            raise TimeoutError("Expected actual heavy execution was not observed")

        attachments = [
            row["attachment"]["id"]
            for row in profile["fixtures"]
            if row["name"]
            in {
                "bearing_inspection_generated_01.jpg",
                "facility_maintenance_handbook.pdf",
                "telemetry_small.csv",
            }
        ]
        job_body = {
            "conversation_id": cid,
            "request_id": uuid.uuid4().hex,
            "content": "Investigate alternative explanations using these synthetic sources. Keep measurements distinct from generated visual observations and identify independent diagnostic checks.",
            "attachment_ids": attachments,
            "mode": "investigate",
        }
        if args.phase == "seed":
            response = api.post("/investigation-jobs", json=job_body)
            response.raise_for_status()
            job = response.json()
            observed = active()
            (out / "restart_seed.json").write_text(
                json.dumps(
                    {"job": job, "conversation_id": cid, "active": observed}, indent=2
                ),
                encoding="utf-8",
            )
            print(
                json.dumps(
                    {
                        "job_id": job["id"],
                        "status": job["status"],
                        "active_observed": True,
                    }
                )
            )
            return
        if args.phase == "recovery":
            seed = json.loads((out / "restart_seed.json").read_text())
            job = api.get(
                "/investigation-jobs/" + seed["job"]["id"],
                params={"conversation_id": cid},
            ).json()
            assert (
                job["status"] == "interrupted"
                and job["error"]["code"] == "process_restarted"
            ), job
            result = {
                "status": "pass",
                "job": job,
                "resources": api.get("/runtime/resources").json(),
            }
            (out / "restart_recovery.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            print(json.dumps({"status": "pass", "job_status": job["status"]}))
            return

        def cancel_gpu():
            rid = uuid.uuid4().hex
            isolated = api.post(
                "/conversations", json={"title": "Disposable active GPU cancellation"}
            ).json()["id"]
            with ThreadPoolExecutor(1) as pool:
                future = pool.submit(
                    chat,
                    "Give a detailed explanation of how rolling bearings reduce friction in general.",
                    rid,
                    None,
                    isolated,
                )
                before = active("conversation", True)
                assert any(
                    m.get("size_vram", 0) > 0
                    for m in before["ollama_residency"]["models"]
                )
                began = time.perf_counter()
                ack = api.post(
                    "/chat/cancel", json={"request_id": rid, "reason": "operator_stop"}
                ).json()
                events = future.result(timeout=20)
                assert (
                    ack["cancellation_requested"]
                    and events[-1]["status"] == "cancelled"
                ), events[-1]
                return {
                    "cancel_to_terminal_seconds": time.perf_counter() - began,
                    "observed_before": before,
                    "events": events,
                    "resources_after": api.get("/runtime/resources").json(),
                }

        record("active_gpu_cancel", cancel_gpu)

        def speech(text, cancel_after_first=False):
            rid = uuid.uuid4().hex
            events = []
            first_ready = None
            began = time.perf_counter()
            with ThreadPoolExecutor(1) as pool:

                def consume():
                    nonlocal first_ready
                    with api.stream(
                        "POST",
                        "/specialists/speech/stream",
                        json={
                            "conversation_id": cid,
                            "request_id": rid,
                            "text": text,
                            "voice_id": 0,
                            "speed": 1,
                        },
                    ) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if line.startswith("data: "):
                                event = json.loads(line[6:])
                                event["received_seconds"] = time.perf_counter() - began
                                if event["type"] == "audio_chunk":
                                    audio = event["audio"]
                                    raw = base64.b64decode(
                                        audio.pop("audio_base64"), validate=True
                                    )
                                    assert (
                                        hashlib.sha256(raw).hexdigest()
                                        == audio["sha256"]
                                    )
                                    file = out / (
                                        rid + "_" + str(event["index"]) + ".wav"
                                    )
                                    file.write_bytes(raw)
                                    audio["actual_audio_path"] = str(
                                        file.relative_to(ROOT)
                                    )
                                    if first_ready is None:
                                        first_ready = event["received_seconds"]
                                events.append(event)

                future = pool.submit(consume)
                cancel_seconds = None
                actual_child_exited = None
                observed = None
                if cancel_after_first:
                    deadline = time.perf_counter() + 65
                    while (
                        first_ready is None
                        and not future.done()
                        and time.perf_counter() < deadline
                    ):
                        time.sleep(0.02)
                    assert first_ready is not None, "No actual first WAV delivered"
                    observed = active("tts")
                    handle = None
                    if os.name == "nt":
                        import ctypes

                        pid = next(
                            e["audio"]["worker_lifecycle"]["process_id"]
                            for e in events
                            if e["type"] == "audio_chunk"
                        )
                        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                        kernel.OpenProcess.restype = ctypes.c_void_p
                        kernel.WaitForSingleObject.argtypes = [
                            ctypes.c_void_p,
                            ctypes.c_uint32,
                        ]
                        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                        handle = kernel.OpenProcess(0x100000, False, pid)
                        assert handle
                    start = time.perf_counter()
                    ack = api.post(
                        "/specialists/cancel",
                        json={"conversation_id": cid, "request_id": rid},
                    ).json()
                    assert ack["cancellation_requested"]
                    future.result(timeout=20)
                    cancel_seconds = time.perf_counter() - start
                    if handle:
                        try:
                            actual_child_exited = (
                                kernel.WaitForSingleObject(handle, 2000) == 0
                            )
                        finally:
                            kernel.CloseHandle(handle)
                        assert actual_child_exited
                    assert events[-1]["status"] == "cancelled", events[-1]
                else:
                    future.result(timeout=150)
                    assert events[-1]["status"] == "complete", events[-1]
                return {
                    "first_completed_wav_seconds": first_ready,
                    "total_seconds": time.perf_counter() - began,
                    "cancel_to_terminal_seconds": cancel_seconds,
                    "actual_child_exited": actual_child_exited,
                    "observed_before_cancel": observed,
                    "events": events,
                }

        text = "Independent inspection is required. Record the measured pressure."
        record("fresh_sentence_stream", lambda: speech(text))
        record(
            "cancel_active_speech",
            lambda: speech(
                "Hello. Independent inspection and a review of the original sensor measurements and maintenance records are required before any physical failure mechanism can be confirmed.",
                True,
            ),
        )
        record("cached_sentence_stream", lambda: speech(text))

        def concurrent():
            response = api.post("/investigation-jobs", json=job_body)
            response.raise_for_status()
            job = response.json()
            before = active()
            times = {}
            for label, operation in [
                (
                    "status",
                    lambda: api.get(
                        "/investigation-jobs/" + job["id"],
                        params={"conversation_id": cid},
                    ).json(),
                ),
                ("greeting", lambda: chat("Hello, SIRE")),
                ("saved_followup_1", lambda: chat("Show saved hypotheses.")),
                ("saved_followup_2", lambda: chat("Explain previous findings.")),
                (
                    "upload",
                    lambda: api.post(
                        "/attachments",
                        data={"conversation_id": cid},
                        files={
                            "file": (
                                "TEST-ONLY-concurrent-reference.txt",
                                b"This is a test-only record for concurrent file acceptance. It is not a measurement or fault finding.",
                            )
                        },
                    ).json(),
                ),
                (
                    "duplicate_job",
                    lambda: api.post("/investigation-jobs", json=job_body).json(),
                ),
            ]:
                start = time.perf_counter()
                value = operation()
                times[label] = {"seconds": time.perf_counter() - start, "result": value}
            assert times["duplicate_job"]["result"]["id"] == job["id"]
            for label in ["greeting", "saved_followup_1", "saved_followup_2"]:
                assert not times[label]["result"][-1]["metadata"].get(
                    "model_activity"
                ), times[label]
            deadline = time.perf_counter() + 280
            while (
                job["status"] in {"queued", "running"}
                and time.perf_counter() < deadline
            ):
                time.sleep(0.25)
                job = api.get(
                    "/investigation-jobs/" + job["id"], params={"conversation_id": cid}
                ).json()
            assert job["status"] == "complete", job
            return {
                "active_before": before,
                "operations": times,
                "job": job,
                "trace": api.get("/runs/" + job["run_id"] + "/trace").json(),
            }

        record("concurrent_status_upload_recall_dedup", concurrent)

        def outage():
            isolated = api.post(
                "/conversations", json={"title": "Disposable provider outage"}
            ).json()["id"]
            events = chat(
                "Explain friction in two short sentences.",
                model="TEST-ONLY-nonexistent-model",
                conversation_id=isolated,
            )
            assert events[-1]["status"] == "error" and not any(
                e.get("type") == "delta" for e in events
            ), events
            return events

        record("actual_unavailable_tag", outage)
        proof["resources_after"] = api.get("/runtime/resources").json()
        save()
    if any(row["status"] == "failed" for row in proof["cases"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
