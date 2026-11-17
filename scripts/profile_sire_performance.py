"""Bounded real loopback/Ollama benchmarks; never mix benchmark records into production state."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid
import wave

import httpx

ROOT = Path(__file__).resolve().parents[1]
QUESTION = "In two short sentences, explain how rolling bearings reduce friction. No machine-specific measurements are supplied."


def main() -> None:
    """Measure actual phase timings and resource observations, retaining errors without fake passes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ollama", default="http://127.0.0.1:11434")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--direct-only", action="store_true")
    parser.add_argument("--deep-only", action="store_true")
    args = parser.parse_args()
    if args.direct_only and args.deep_only:
        parser.error("Choose one profile subset")
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / ".runtime/performance_20261118").resolve()):
        raise SystemExit("Use a new performance-only output directory")
    output.mkdir(parents=True, exist_ok=False)
    proof = {
        "scope": "Real loopback services and file audio; browser render, microphone and first audible time unmeasured. OS caches not flushed.",
        "cases": [],
        "samples": [],
    }
    stop = threading.Event()
    beginning = time.monotonic()

    def monitor():
        with httpx.Client(timeout=2, trust_env=False) as client:
            while not stop.is_set():
                row = {"elapsed_seconds": time.monotonic() - beginning}
                try:
                    row["gpu"] = subprocess.check_output(
                        [
                            "nvidia-smi",
                            "--query-gpu=memory.used,utilization.gpu",
                            "--format=csv,noheader,nounits",
                        ],
                        text=True,
                    ).strip()
                    row["ollama_ps"] = client.get(args.ollama + "/api/ps").json()
                except Exception as exc:
                    row["error"] = type(exc).__name__
                proof["samples"].append(row)
                stop.wait(1)

    def save():
        (output / "results.json").write_text(
            json.dumps(proof, indent=2), encoding="utf-8"
        )

    def record(name, operation):
        began = time.monotonic()
        try:
            value = operation()
            row = {"name": name, "status": "completed", "result": value}
        except Exception as exc:
            row = {
                "name": name,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
        row["elapsed_seconds"] = time.monotonic() - began
        proof["cases"].append(row)
        save()
        print(
            json.dumps(
                {key: row[key] for key in ["name", "status", "elapsed_seconds"]}
            ),
            flush=True,
        )
        return row

    monitor_thread = threading.Thread(target=monitor)
    monitor_thread.start()
    try:
        with (
            httpx.Client(timeout=310, trust_env=False) as raw,
            httpx.Client(
                base_url="http://127.0.0.1:8001/api/v1", timeout=310, trust_env=False
            ) as api,
        ):
            tags = raw.get(args.ollama + "/api/tags").json()
            proof["installed_models"] = tags
            proof["ollama_before"] = raw.get(args.ollama + "/api/ps").json()

            def unload():
                for model in raw.get(args.ollama + "/api/ps").json().get("models", []):
                    raw.post(
                        args.ollama + "/api/generate",
                        json={"model": model["name"], "keep_alive": 0},
                    ).raise_for_status()

            unload()

            def direct():
                began = time.monotonic()
                first = None
                answer = ""
                last = {}
                with raw.stream(
                    "POST",
                    args.ollama + "/api/chat",
                    json={
                        "model": "qwen3:4b-instruct",
                        "messages": [
                            {
                                "role": "system",
                                "content": "Answer concisely in two sentences. Do not invent measurements or citations.",
                            },
                            {"role": "user", "content": QUESTION},
                        ],
                        "stream": True,
                        "think": False,
                        "keep_alive": "30s",
                        "options": {
                            "temperature": 0,
                            "seed": 42,
                            "num_ctx": 4096,
                            "num_predict": 160,
                        },
                    },
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        item = json.loads(line)
                        token = item.get("message", {}).get("content", "")
                        if token:
                            if first is None:
                                first = time.monotonic() - began
                            answer += token
                        if item.get("done"):
                            last = item
                return {
                    "first_token_seconds": first,
                    "response_seconds": time.monotonic() - began,
                    "answer": answer,
                    "metrics": last,
                    "residency_after": raw.get(args.ollama + "/api/ps").json(),
                    "ollama_ps_cli": subprocess.check_output(
                        [
                            str(
                                Path.home()
                                / "AppData/Local/Programs/SIRE-Ollama/ollama.exe"
                            ),
                            "ps",
                        ],
                        env={**os.environ, "OLLAMA_HOST": args.ollama},
                        text=True,
                    ),
                }

            if not args.deep_only:
                record("direct_residency_cold", direct)
                record("direct_same_prompt_resident_warm", direct)
                unload()
            if args.direct_only:
                return
            cid = api.post(
                "/conversations", json={"title": "Disposable performance profile"}
            ).json()["id"]
            proof["conversation_id"] = cid

            def turn(question, attachment_ids=None, **extra):
                began = time.monotonic()
                events = []
                with api.stream(
                    "POST",
                    "/chat/message",
                    json={
                        "conversation_id": cid,
                        "request_id": uuid.uuid4().hex,
                        "content": question,
                        "attachment_ids": attachment_ids or [],
                        **extra,
                    },
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if line.startswith("data: "):
                            events.append(
                                {
                                    **json.loads(line[6:]),
                                    "received_seconds": time.monotonic() - began,
                                }
                            )
                assert events[-1]["type"] == "done", events
                return {
                    "events": events,
                    "first_text_seconds": next(
                        (e["received_seconds"] for e in events if e["type"] == "delta"),
                        None,
                    ),
                    "response_seconds": time.monotonic() - began,
                    "trace": api.get(
                        "/runs/"
                        + events[-1]["metadata"]["orchestration"]["run_id"]
                        + "/trace"
                    ).json(),
                }

            if not args.deep_only:
                record("app_general_cold", lambda: turn(QUESTION))
                record("app_general_repeat", lambda: turn(QUESTION))

            def voice():
                path = args.corpus / "media/audio/spoken_question_en.wav"
                began = time.monotonic()
                response = api.post(
                    "/attachments",
                    data={"conversation_id": cid},
                    files={"file": (path.name, path.read_bytes(), "audio/wav")},
                )
                response.raise_for_status()
                receipt = response.json()
                asr_seconds = time.monotonic() - began
                transcript = receipt["metadata"].get("transcript")
                assert transcript, receipt
                chat = turn(
                    transcript["text"],
                    [receipt["id"]],
                    input_audio_id=receipt["id"],
                    voice_response=True,
                )
                meta = chat["events"][-1]["metadata"]
                assert chat["events"][-1]["status"] == "complete", chat
                answer = meta.get("speech_text") or "".join(
                    e.get("text", "") for e in chat["events"] if e["type"] == "delta"
                )
                tts_began = time.monotonic()
                audio = api.post(
                    "/voice/speak",
                    json={"text": answer[:220], "request_id": uuid.uuid4().hex},
                )
                audio.raise_for_status()
                tts_seconds = time.monotonic() - tts_began
                (output / "voice_reply.wav").write_bytes(audio.content)
                with wave.open(io.BytesIO(audio.content), "rb") as wav:
                    frames, rate = wav.getnframes(), wav.getframerate()
                return {
                    "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "transcript": transcript,
                    "asr_intake_seconds": asr_seconds,
                    "chat": chat,
                    "tts_seconds": tts_seconds,
                    "tts_model": audio.headers.get("X-Speech-Model"),
                    "tts_cache": audio.headers.get("X-Speech-Cache"),
                    "tts_phase_timings": audio.headers.get("X-Speech-Phase-Timings"),
                    "frames": frames,
                    "sample_rate": rate,
                    "end_to_end_seconds": time.monotonic() - began,
                    "first_audible_seconds": None,
                }

            if not args.deep_only:
                record("voice_actual_file_roundtrip", voice)

            def deep():
                ids = []
                for relative in [
                    "media/images/bearing_inspection_generated_01.jpg",
                    "documents/facility_maintenance_handbook.pdf",
                    "test_inputs/valid/telemetry_small.csv",
                ]:
                    path = args.corpus / relative
                    r = api.post(
                        "/attachments",
                        data={"conversation_id": cid},
                        files={"file": (path.name, path.read_bytes())},
                    )
                    r.raise_for_status()
                    ids.append(r.json()["id"])
                began = time.monotonic()
                r = api.post(
                    "/investigation-jobs",
                    json={
                        "conversation_id": cid,
                        "request_id": uuid.uuid4().hex,
                        "content": "Compare possible mechanisms using this visually generated test photograph, maintenance manual and synthetic CSV. Preserve alternatives and missing asset association; do not treat an image as proof of hidden damage.",
                        "attachment_ids": ids,
                        "mode": "investigate",
                    },
                )
                r.raise_for_status()
                job = r.json()
                accepted = time.monotonic() - began
                first = None
                while True:
                    job = api.get(
                        "/investigation-jobs/" + job["id"] + "?conversation_id=" + cid
                    ).json()
                    if first is None and any(
                        e.get("source")
                        == "validated_descriptive_measurement_statistics"
                        for e in job["events"]
                    ):
                        first = time.monotonic() - began
                    if job["status"] not in ["queued", "running"]:
                        break
                    if time.monotonic() - began > 305:
                        api.post(
                            "/investigation-jobs/"
                            + job["id"]
                            + "/cancel?conversation_id="
                            + cid,
                            json={},
                        )
                        raise TimeoutError("Bounded deep benchmark exceeded305s")
                    time.sleep(0.5)
                return {
                    "accepted_seconds": accepted,
                    "first_verified_facts_poll_upper_bound": first,
                    "response_seconds": time.monotonic() - began,
                    "job": job,
                    "trace": api.get("/runs/" + job["run_id"] + "/trace").json(),
                }

            record("deep_multimodal", deep)
            proof["resources_after"] = api.get("/runtime/resources").json()
            save()
    finally:
        stop.set()
        monitor_thread.join()
        save()


if __name__ == "__main__":
    main()
