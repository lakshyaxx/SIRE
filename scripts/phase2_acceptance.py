"""Real serial Phase 2 local specialist acceptance, confined to an explicit test database."""

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import uuid
import wave
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    """Run existing specialist acceptance against a guarded disposable local namespace."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8001/api/v1")
    parser.add_argument("--short-audio", type=Path, required=True)
    args = parser.parse_args()
    state = args.state_dir.resolve()
    output = args.output.resolve()
    if (
        not state.is_relative_to(ROOT / ".runtime")
        or state == ROOT / ".runtime/v2"
        or not output.is_relative_to(ROOT / ".runtime")
    ):
        raise SystemExit("Require explicit disposable state and private output")
    if args.api != "http://127.0.0.1:8001/api/v1":
        raise SystemExit("This harness is restricted to the disposable 8001 listener")
    output.mkdir(parents=True, exist_ok=False)
    proof = {
        "scope": "Actual local network and recorded file media. Physical microphone/speaker/browser acceptance not claimed. No evaluator files accessed.",
        "cases": [],
    }

    def save():
        (output / "results.json").write_text(
            json.dumps(proof, indent=2), encoding="utf-8"
        )

    def record(name, operation):
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
        row["elapsed_seconds"] = time.perf_counter() - began
        proof["cases"].append(row)
        save()
        print(
            json.dumps({k: row[k] for k in ["name", "status", "elapsed_seconds"]}),
            flush=True,
        )
        return row

    with httpx.Client(base_url=args.api, timeout=310, trust_env=False) as api:
        contracts = api.get("/specialists/contracts")
        contracts.raise_for_status()
        expected = hashlib.sha256(
            str((state / "sire.sqlite3").resolve()).encode()
        ).hexdigest()
        assert (
            contracts.json()["state_namespace"] == expected
        ), "Refuse to write to an unexpected database"
        proof["contracts"] = contracts.json()
        proof["health"] = api.get("/health").json()
        cid = api.post(
            "/conversations", json={"title": "Disposable Phase 2 specialist acceptance"}
        ).json()["id"]
        proof["conversation_id"] = cid

        def upload(path):
            if "evaluator_only" in path.parts:
                raise ValueError("Evaluator data forbidden")
            data = path.read_bytes()
            r = api.post(
                "/attachments",
                data={"conversation_id": cid},
                files={"file": (path.name, data)},
            )
            r.raise_for_status()
            result = r.json()
            proof.setdefault("fixtures", []).append(
                {
                    "path": str(path),
                    "original_sha256": hashlib.sha256(data).hexdigest(),
                    "attachment_id": result["id"],
                }
            )
            save()
            return result

        def call(tool, arguments):
            r = api.post(
                "/specialists/execute",
                json={
                    "conversation_id": cid,
                    "request_id": uuid.uuid4().hex,
                    "tool_id": tool,
                    "arguments": arguments,
                },
            )
            r.raise_for_status()
            value = r.json()
            assert value["status"] == "complete", value
            trace = api.get("/runs/" + value["run_id"] + "/trace")
            trace.raise_for_status()
            return {"response": value, "trace": trace.json()}

        def chat(text):
            began = time.perf_counter()
            events = []
            with api.stream(
                "POST",
                "/chat/message",
                json={
                    "conversation_id": cid,
                    "content": text,
                    "request_id": uuid.uuid4().hex,
                },
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        events.append(
                            {
                                **json.loads(line[6:]),
                                "received_seconds": time.perf_counter() - began,
                            }
                        )
            assert (
                events[-1]["type"] == "done" and events[-1]["status"] == "complete"
            ), events
            assert not events[-1]["metadata"].get("model_activity"), events[-1]
            return {
                "events": events,
                "first_text_seconds": next(
                    (e["received_seconds"] for e in events if e["type"] == "delta"),
                    None,
                ),
            }

        record("01_greeting_no_model", lambda: chat("Hello, SIRE"))
        record("02_documented_capabilities_no_model", lambda: chat("What can you do?"))

        def image():
            item = upload(
                args.corpus / "media/images/bearing_inspection_generated_01.jpg"
            )
            return call(
                "vision.inspect",
                {
                    "attachment_id": item["id"],
                    "text": "This is a visually generated test photograph. Describe visible observations, the visual type and uncertainty; it cannot prove an internal physical failure.",
                },
            )

        record("03_image_only", image)

        def document(relative):
            item = upload(args.corpus / relative)
            return call("document.extract", {"attachment_id": item["id"]})

        record(
            "04_pdf_extraction",
            lambda: document("documents/facility_maintenance_handbook.pdf"),
        )

        def csv():
            item = upload(args.corpus / "test_inputs/valid/telemetry_small.csv")
            return call("measurements.profile", {"attachment_id": item["id"]})

        record("05_csv_statistics", csv)
        record(
            "06_xlsx_interpretation",
            lambda: document("documents/sire_maintenance_workbook.xlsx"),
        )

        def audio(path):
            item = upload(path)
            result = call("audio.transcript", {"attachment_id": item["id"]})
            assert (
                result["response"]["output_role"] == "input_provenance"
                and not result["response"]["evidence_ids"]
            )
            return result

        record("07_short_speech", lambda: audio(args.short_audio))
        record(
            "08_industrial_speech",
            lambda: audio(args.corpus / "media/audio/pump_report_en.wav"),
        )

        def speech():
            result = call(
                "speech.synthesize",
                {
                    "text": "Independent inspection is required before confirming a fault.",
                    "voice_id": 1,
                    "speed": 1,
                },
            )
            value = result["response"]["output"]["audio"]
            data = base64.b64decode(value["audio_base64"], validate=True)
            assert hashlib.sha256(data).hexdigest() == value["sha256"]
            with wave.open(io.BytesIO(data), "rb") as wav:
                assert (
                    wav.getnframes() == value["frames"]
                    and wav.getframerate() == value["sample_rate"]
                )
            (output / "actual_speech.wav").write_bytes(data)
            return result

        record("09_new_configured_voice_synthesis", speech)

        def video():
            item = upload(args.corpus / "media/video/bearing_inspection_pan.mp4")
            result = call(
                "video.inspect",
                {
                    "attachment_id": item["id"],
                    "text": "Inspect these sampled frames of a generated inspection fixture. Report visible observations only; do not infer unseen motion or hidden failure.",
                },
            )
            v = result["response"]["output"]
            assert v["frames"] and len(v["frames"]) <= 3
            result["child_trace"] = api.get(
                "/runs/" + v["video"]["child_run_id"] + "/trace"
            ).json()
            return result

        record("10_sampled_video", video)

        def native():
            from app.prediction.policy import selections

            values = []
            for dataset, roles in selections().items():
                for role, model in roles.items():
                    result = call(
                        "prediction.run",
                        {
                            "dataset": dataset,
                            "model_id": model,
                            "asset_id": dataset + "-ENGINE-001",
                        },
                    )
                    values.append({"dataset": dataset, "role": role, **result})
                    proof["native_in_progress"] = values
                    save()
            assert len(values) == 12
            return values

        record("16_native_all_primary_saved_pathways", native)
        proof["resources_after"] = api.get("/runtime/resources").json()
        save()
    if any(c["status"] == "failed" for c in proof["cases"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
