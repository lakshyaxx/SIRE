"""Bounded real network profiling in an explicitly verified disposable namespace."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEXT = "In two short sentences, explain how rolling bearings reduce friction. No machine-specific measurements are supplied."
SPEECH = [
    "Hello. How can I help?",
    "Hello. What can I explain?",
    "Independent inspection is required. Record the measured pressure.",
    "The available evidence does not establish a confirmed failure mechanism. Review the original measurements, check the instrument calibration, and compare the maintenance records before selecting a diagnostic inspection.",
]


def main() -> None:
    """Record actual answers, traces, input hashes and usable output latency without estimates."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--short-audio", type=Path, required=True)
    args = parser.parse_args()
    state, out = args.state_dir.resolve(), args.output.resolve()
    if (
        not state.is_relative_to(ROOT / ".runtime")
        or state == ROOT / ".runtime/v2"
        or not out.is_relative_to(ROOT / ".runtime")
        or "evaluator_only" in args.corpus.parts
    ):
        raise SystemExit("Require isolated public inputs and disposable state/output")
    out.mkdir(exist_ok=False)
    proof = {
        "scope": "Actual local network; small paired workload, no physical-audio or universal diagnostic-accuracy claim.",
        "cases": [],
        "fixtures": [],
    }

    def save() -> None:
        (out / "results.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")

    def record(name, operation, **conditions):
        began = time.perf_counter()
        try:
            result = operation()
            row = {"name": name, "status": "passed", "result": result}
        except Exception as exc:
            row = {
                "name": name,
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }
        row.update(seconds=time.perf_counter() - began, conditions=conditions)
        proof["cases"].append(row)
        save()
        print(
            json.dumps({k: row[k] for k in ["name", "status", "seconds"]}), flush=True
        )
        return row

    with httpx.Client(
        base_url="http://127.0.0.1:8001/api/v1", timeout=330, trust_env=False
    ) as api:
        contract = api.get("/specialists/contracts")
        contract.raise_for_status()
        assert (
            contract.json()["state_namespace"]
            == hashlib.sha256(
                str((state / "sire.sqlite3").resolve()).encode()
            ).hexdigest()
        )
        proof["contracts"] = contract.json()
        proof["health"] = api.get("/health").json()
        cid = api.post(
            "/conversations", json={"title": "Disposable paired Phase 3 profile"}
        ).json()["id"]
        proof["conversation_id"] = cid

        def upload(path):
            assert "evaluator_only" not in path.parts
            data = path.read_bytes()
            began = time.perf_counter()
            response = api.post(
                "/attachments",
                data={"conversation_id": cid},
                files={"file": (path.name, data)},
            )
            response.raise_for_status()
            item = response.json()
            proof["fixtures"].append(
                {
                    "name": path.name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                    "upload_seconds": time.perf_counter() - began,
                    "attachment": item,
                }
            )
            return item

        def tool(identifier, arguments):
            response = api.post(
                "/specialists/execute",
                json={
                    "conversation_id": cid,
                    "request_id": uuid.uuid4().hex,
                    "tool_id": identifier,
                    "arguments": arguments,
                },
            )
            response.raise_for_status()
            result = response.json()
            assert result["status"] == "complete", result
            audio = (result.get("output") or {}).get("audio")
            if audio:
                data = base64.b64decode(audio.pop("audio_base64"), validate=True)
                assert hashlib.sha256(data).hexdigest() == audio["sha256"]
                file = out / (result["request_id"] + ".wav")
                file.write_bytes(data)
                audio["actual_audio_path"] = str(file.relative_to(ROOT))
                audio["real_time_factor"] = (
                    result["elapsed_seconds"] / audio["duration_seconds"]
                )
            trace = api.get("/runs/" + result["run_id"] + "/trace")
            trace.raise_for_status()
            return {"response": result, "trace": trace.json()}

        def chat(text):
            began = time.perf_counter()
            events = []
            with api.stream(
                "POST",
                "/chat/message",
                json={
                    "conversation_id": cid,
                    "request_id": uuid.uuid4().hex,
                    "content": text,
                },
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        events.append(
                            {
                                **json.loads(line[6:]),
                                "received_seconds": time.perf_counter() - began,
                            }
                        )
            assert events[-1]["status"] == "complete", events[-1]
            return {
                "first_text_seconds": next(
                    (e["received_seconds"] for e in events if e["type"] == "delta"),
                    None,
                ),
                "events": events,
            }

        with httpx.Client(timeout=30, trust_env=False) as ollama:
            for model in ollama.get("http://127.0.0.1:11434/api/ps").json()["models"]:
                ollama.post(
                    "http://127.0.0.1:11434/api/generate",
                    json={"model": model["name"], "keep_alive": 0},
                ).raise_for_status()
        record(
            "text_cold",
            lambda: chat(TEXT),
            state="unloaded residency; OS caches unchanged",
        )
        record(
            "text_warm", lambda: chat(TEXT), state="resident; paired history follow-up"
        )
        record("greeting", lambda: chat("Hello, SIRE"), expected="no model")
        record(
            "capabilities",
            lambda: chat("What can you do?"),
            expected="documented manifest",
        )

        pdf = upload(args.corpus / "documents/facility_maintenance_handbook.pdf")
        csv = upload(args.corpus / "test_inputs/valid/telemetry_small.csv")
        xlsx = upload(args.corpus / "documents/sire_maintenance_workbook.xlsx")
        docx = upload(args.corpus / "documents/maintenance_work_order.docx")
        for name, item, identifier in [
            ("pdf", pdf, "document.extract"),
            ("csv", csv, "measurements.profile"),
            ("xlsx", xlsx, "document.extract"),
            ("docx", docx, "document.extract"),
        ]:
            record(
                name,
                lambda item=item, identifier=identifier: tool(
                    identifier, {"attachment_id": item["id"]}
                ),
                state="fresh source extraction",
            )
        for name in ["retrieval_first", "retrieval_repeat"]:
            record(
                name,
                lambda: tool(
                    "knowledge.retrieve",
                    {
                        "text": "lubrication pressure vibration maintenance",
                        "mode": "hybrid",
                        "attachment_ids": [pdf["id"], docx["id"]],
                    },
                ),
                state="persistent chunk vectors; fresh query inference",
            )
        for name, path, profile in [
            ("asr_short", args.short_audio, None),
            (
                "asr_technical_base",
                args.corpus / "media/audio/pump_report_en.wav",
                None,
            ),
            (
                "asr_technical_tiny",
                args.corpus / "media/audio/pump_report_en.wav",
                "asr",
            ),
        ]:
            item = upload(path)
            record(
                name,
                lambda item=item: tool(
                    "audio.transcript", {"attachment_id": item["id"]}
                ),
                profile=profile,
                original_sha256=item["sha256"],
            )
            # The explicit tiny comparison uses the original transcription endpoint,
            # because upload transcription follows the configured default model.
            if profile:
                response = api.post(
                    "/voice/transcribe",
                    params={"profile": profile},
                    files={"file": (path.name, path.read_bytes())},
                )
                proof["cases"][-1]["explicit_profile_response"] = {
                    "status_code": response.status_code,
                    "result": response.json(),
                }
                save()
        for index, text in enumerate(SPEECH):
            record(
                "tts_" + str(index),
                lambda text=text: tool(
                    "speech.synthesize", {"text": text, "voice_id": 0, "speed": 1}
                ),
                input=text,
                characters=len(text),
                cache="must be fresh exact text in a new server process",
            )
        image = upload(args.corpus / "media/images/bearing_inspection_generated_01.jpg")
        record(
            "image",
            lambda: tool(
                "vision.inspect",
                {
                    "attachment_id": image["id"],
                    "text": "Describe visible observations and visual type only; this generated fixture cannot establish hidden damage.",
                },
            ),
            state="fresh VLM call after text; no result cache",
        )
        record("vision_to_text", lambda: chat(TEXT), state="model family transition")
        video = upload(args.corpus / "media/video/bearing_inspection_pan.mp4")
        record(
            "video",
            lambda: tool(
                "video.inspect",
                {
                    "attachment_id": video["id"],
                    "text": "Describe these sparse generated inspection frames without inferring unseen events.",
                },
            ),
            state="fresh three-frame calls",
        )

        from app.prediction.policy import selections

        providers = api.get("/providers/registry").json()["providers"]
        selected = selections()
        wanted = {
            "native:" + model for roles in selected.values() for model in roles.values()
        }
        proof["primary_provider_inventory"] = [
            row for row in providers if row["id"] in wanted
        ]
        for role, model in selected["FD001"].items():
            record(
                "rul_" + role,
                lambda model=model: tool(
                    "prediction.run",
                    {
                        "dataset": "FD001",
                        "model_id": model,
                        "asset_id": "FD001-ENGINE-001",
                    },
                ),
                state="genuine existing compatible saved history; no synthetic telemetry",
            )

        def deep():
            began = time.perf_counter()
            response = api.post(
                "/investigation-jobs",
                json={
                    "conversation_id": cid,
                    "request_id": uuid.uuid4().hex,
                    "content": "Investigate alternative explanations from this generated photo, synthetic telemetry and reference manual. Keep unlinked assets explicit. A photograph cannot establish hidden damage.",
                    "attachment_ids": [image["id"], pdf["id"], csv["id"]],
                    "mode": "investigate",
                },
            )
            response.raise_for_status()
            job = response.json()
            first = None
            concurrent = None
            while job["status"] in {"queued", "running"}:
                if (
                    concurrent is None
                    and api.get("/runtime/resources").json()["scheduler"]["active"]
                ):
                    start = time.perf_counter()
                    greeting = chat("Hello, SIRE")
                    concurrent = {
                        "seconds": time.perf_counter() - start,
                        "greeting": greeting,
                    }
                if first is None and any(
                    e.get("source") == "validated_descriptive_measurement_statistics"
                    for e in job.get("events", [])
                ):
                    first = time.perf_counter() - began
                if time.perf_counter() - began > 310:
                    api.post(
                        "/investigation-jobs/" + job["id"] + "/cancel",
                        params={"conversation_id": cid},
                        json={},
                    )
                    raise TimeoutError("Bounded investigation deadline exceeded")
                time.sleep(0.25)
                job = api.get(
                    "/investigation-jobs/" + job["id"], params={"conversation_id": cid}
                ).json()
            assert job["status"] == "complete", job
            return {
                "job": job,
                "first_facts_poll_upper_bound": first,
                "concurrent": concurrent,
                "trace": api.get("/runs/" + job["run_id"] + "/trace").json(),
            }

        record(
            "deep",
            deep,
            state="fresh job and uncached question; native CUDA OS caches not cleared",
        )
        proof["resources_after"] = api.get("/runtime/resources").json()
        save()
    if any(row["status"] == "failed" for row in proof["cases"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
