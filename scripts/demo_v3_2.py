"""Real application demonstrations A/B/C plus local voice/video; no canned model responses."""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import wave
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    """Call actual loopback contracts, assert content/provenance, preserve every failed run."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8001")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=[
            "normal_chat",
            "demo_A_predictive_maintenance",
            "demo_B_visual_investigation",
            "demo_C_reconstruction",
            "voice_same_chat_pipeline",
            "bounded_video_actual_frames_and_vision",
        ],
    )
    parser.add_argument(
        "--reuse-photo-evidence",
        action="store_true",
        help="Reuse exact actual source extraction in latest photo demo; hypothesis generation is still fresh",
    )
    args = parser.parse_args()
    if args.base.rstrip("/") not in {"http://127.0.0.1:8000", "http://127.0.0.1:8001"}:
        raise SystemExit("Use the local application on 8000/8001 only.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    directory = ROOT / "output/v3_2" / stamp
    directory.mkdir(parents=True)
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": {},
        "verification_scope": "Actual API/content/model/media checks; browser/microphone/speaker interaction not exercised.",
    }

    def save() -> None:
        text = json.dumps(result, indent=2)
        (directory / "results.json").write_text(text, encoding="utf-8")
        (ROOT / "docs/V3_2_LIVE_RESULTS.json").write_text(text, encoding="utf-8")

    with httpx.Client(base_url=args.base, timeout=310, trust_env=False) as client:

        def conversation(title: str) -> str:
            return (
                client.post(
                    "/api/v1/conversations", json={"title": "[V3.2 real demo] " + title}
                )
                .raise_for_status()
                .json()["id"]
            )

        def upload(cid: str, name: str, content: bytes) -> dict:
            value = (
                client.post(
                    "/api/v1/attachments",
                    data={"conversation_id": cid},
                    files={"file": (name, content)},
                )
                .raise_for_status()
                .json()
            )
            if value["metadata"].get("media_error"):
                raise RuntimeError(json.dumps(value["metadata"]["media_error"]))
            return value

        def chat(
            cid: str,
            question: str,
            attachments: list[str] | None = None,
            scope: dict | None = None,
        ) -> dict:
            began = time.monotonic()
            response = client.post(
                "/api/v1/chat/message",
                json={
                    "conversation_id": cid,
                    "content": question,
                    "attachment_ids": attachments or [],
                    "context": scope,
                },
            ).raise_for_status()
            events = [
                json.loads(line[6:])
                for line in response.text.splitlines()
                if line.startswith("data: ")
            ]
            value = {
                "events": events,
                "elapsed_seconds": time.monotonic() - began,
                "conversation_id": cid,
            }
            (directory / ("chat-" + str(time.time_ns()) + ".json")).write_text(
                json.dumps(value, indent=2), encoding="utf-8"
            )
            if not events or events[-1].get("status") != "complete":
                raise RuntimeError("Actual chat incomplete: " + json.dumps(events[-2:]))
            value["metadata"] = events[-1]["metadata"]
            value["text"] = "".join(
                event["text"] for event in events if event["type"] == "delta"
            ) or next(
                (event["content"] for event in events if event["type"] == "report"), ""
            )
            value["trace"] = (
                client.get(
                    "/api/v1/runs/"
                    + value["metadata"]["orchestration"]["run_id"]
                    + "/trace"
                )
                .raise_for_status()
                .json()
            )
            return value

        def check(name: str, function) -> None:
            if args.only and name not in args.only:
                return
            began = time.monotonic()
            try:
                result["checks"][name] = {
                    "status": "PASS",
                    "result": function(),
                    "elapsed_seconds": time.monotonic() - began,
                }
            except Exception as exc:
                result["checks"][name] = {
                    "status": "FAIL",
                    "error": str(exc),
                    "elapsed_seconds": time.monotonic() - began,
                }
            save()
            print(
                name,
                result["checks"][name]["status"],
                result["checks"][name]["elapsed_seconds"],
                flush=True,
            )

        result["health"] = client.get("/api/v1/health").raise_for_status().json()
        result["capabilities"] = (
            client.get("/api/v1/capabilities").raise_for_status().json()
        )

        def normal_chat() -> dict:
            value = chat(
                conversation("normal routing"),
                "Hello. Briefly explain how evidence differs from a hypothesis.",
            )
            assert value["text"] and [
                step["tool_id"] for step in value["trace"]["steps"]
            ] == ["llm.chat"]
            return value

        check("normal_chat", normal_chat)

        def predictive() -> dict:
            predictions = []
            for dataset in ["FD001", "FD002", "FD003", "FD004"]:
                models = (
                    client.get(
                        "/api/v1/predictions/models", params={"dataset": dataset}
                    )
                    .raise_for_status()
                    .json()["models"]
                )
                model = next(row for row in models if row["default"])
                prediction = (
                    client.post(
                        "/api/v1/predictions/run",
                        json={
                            "dataset": dataset,
                            "model_id": model["model_id"],
                            "asset_id": dataset + "-ENGINE-001",
                        },
                    )
                    .raise_for_status()
                    .json()
                )
                assert (
                    prediction["dataset"] == dataset
                    and prediction["rul_cycles"] is not None
                    and prediction["provenance"]["runtime"] == "cpu"
                )
                predictions.append(prediction)
            models = (
                client.get("/api/v1/predictions/models", params={"dataset": "FD001"})
                .raise_for_status()
                .json()["models"]
            )
            selected = [row["model_id"] for row in models if row["task"] == "rul"][:2]
            compared = (
                client.post(
                    "/api/v1/predictions/compare",
                    json={
                        "dataset": "FD001",
                        "model_ids": selected,
                        "asset_id": "FD001-ENGINE-001",
                    },
                )
                .raise_for_status()
                .json()
            )
            assert len(compared["results"]) == 2 and all(
                row.get("result") for row in compared["results"]
            )
            return {"predictions": predictions, "comparison": compared}

        check("demo_A_predictive_maintenance", predictive)

        def visual_investigation() -> dict:
            if args.reuse_photo_evidence:
                existing = (
                    client.get("/api/v1/conversations")
                    .raise_for_status()
                    .json()["conversations"]
                )
                cid = next(
                    row["id"]
                    for row in existing
                    if "licensed photo and hypothetical symptoms" in row["title"]
                )
                detail = (
                    client.get("/api/v1/conversations/" + cid).raise_for_status().json()
                )
                photo = next(
                    item
                    for item in detail["attachments"]
                    if item["name"] == "licensed-bearing-demo.jpg"
                )
                note = next(
                    item
                    for item in detail["attachments"]
                    if item["name"] == "demonstration-limitations.txt"
                )
            else:
                cid = conversation("licensed photo and hypothetical symptoms")
                photo = upload(
                    cid,
                    "licensed-bearing-demo.jpg",
                    (ROOT / "data/demo/bearing_cc0.jpg").read_bytes(),
                )
                note = upload(
                    cid,
                    "demonstration-limitations.txt",
                    b"Project demonstration note: this is a licensed component photograph. No verified maintenance, lubrication or alignment measurements or independently verified asset identity have been supplied. A photo alone cannot establish internal damage or RUL.",
                )
            value = chat(
                cid,
                "Investigate the attached licensed demonstration photograph. Hypothetically the operator reports intermittent bearing noise under load; that is a simulated user claim, not a measured incident. Compare plausible mechanisms and missing discriminating measurements. Cite only actual supplied evidence.",
                [photo["id"], note["id"]],
            )
            meta = value["metadata"]
            assert any(item["modality"] == "image" for item in meta["evidence"])
            assert any(item["modality"] == "document" for item in meta["evidence"])
            assert len(meta["investigation"]["hypotheses"]) >= 2
            assert len(
                {item["id"] for item in meta["investigation"]["hypotheses"]}
            ) == len(meta["investigation"]["hypotheses"])
            for item in meta["evidence"]:
                client.get("/api/v1/evidence/" + item["id"]).raise_for_status()
            exported = chat(cid, "Export this investigation report as PDF")
            report_id = exported["metadata"]["generic_report"]["id"]
            pdf = (
                client.get(f"/api/v1/reports/{report_id}/download?format=pdf")
                .raise_for_status()
                .content
            )
            assert pdf.startswith(b"%PDF")
            (directory / "uploaded-evidence-report.pdf").write_bytes(pdf)
            return {"investigation": value, "export": exported, "pdf_bytes": len(pdf)}

        check("demo_B_visual_investigation", visual_investigation)

        def reconstruction() -> dict:
            scenario = next(
                row
                for row in client.get("/api/v1/scenarios")
                .raise_for_status()
                .json()["scenarios"]
                if row["name"].endswith("01")
            )
            cid = conversation("historical reconstruction")
            prefixes = []
            for before in [48, 24, 12]:
                cutoff = (
                    datetime.fromisoformat(scenario["reference_at"])
                    - timedelta(hours=before)
                ).isoformat()
                scope = {
                    "scenario_id": scenario["id"],
                    "asset_id": scenario["asset_id"],
                    "as_of": cutoff,
                }
                rows = (
                    client.get(
                        f"/api/v1/assets/{scenario['asset_id']}/telemetry",
                        params={
                            "scenario_id": scenario["id"],
                            "as_of": cutoff,
                            "limit": 5000,
                        },
                    )
                    .raise_for_status()
                    .json()["records"]
                )
                assert rows and all(
                    row["observed_at"] <= cutoff and row["available_at"] <= cutoff
                    for row in rows
                )
                prefixes.append(
                    chat(cid, "Show sensor trends and maintenance records", scope=scope)
                )
            case = chat(
                cid,
                "Investigate this fault, compare competing hypotheses and export an engineering PDF report",
                scope=scope,
            )
            workspace = case["metadata"]["workspace"]
            for identifier in workspace["evidence_ids"]:
                record = (
                    client.get("/api/v1/evidence/" + identifier)
                    .raise_for_status()
                    .json()["evidence"]
                )
                assert record["available_at"] <= scope["as_of"]
            report_id = workspace["outputs"]["case.report"]["report"]["id"]
            pdf = (
                client.get(f"/api/v1/reports/{report_id}/download?format=pdf")
                .raise_for_status()
                .content
            )
            (directory / "facility-reconstruction-report.pdf").write_bytes(pdf)
            changed = chat(
                cid, "What if we service at hour 48?", scope=workspace["context"]
            )
            memory = chat(cid, "Find similar prior cases", scope=workspace["context"])
            return {
                "prefixes": prefixes,
                "investigation": case,
                "what_if": changed,
                "memory": memory,
                "pdf_bytes": len(pdf),
            }

        check("demo_C_reconstruction", reconstruction)

        def voice() -> dict:
            cid = conversation("actual speech through same orchestrator")
            response = client.post(
                "/api/v1/voice/speak",
                json={"text": "Please explain how evidence differs from a hypothesis."},
            ).raise_for_status()
            recording = response.content
            with wave.open(io.BytesIO(recording), "rb") as audio:
                duration = audio.getnframes() / audio.getframerate()
            uploaded = upload(cid, "actual-generated-question.wav", recording)
            transcript = uploaded["metadata"]["transcript"]
            assert "evidence" in transcript["text"].casefold()
            answer = chat(cid, transcript["text"], [uploaded["id"]])
            assert any(
                step["tool_id"] == "audio.transcript"
                for step in answer["trace"]["steps"]
            )
            speech = client.post(
                "/api/v1/voice/speak", json={"text": answer["text"][:600]}
            ).raise_for_status()
            assert speech.content.startswith(b"RIFF")
            (directory / "actual-reply-audio.wav").write_bytes(speech.content)
            return {
                "question_audio_duration_seconds": duration,
                "transcript": transcript,
                "answer": answer,
                "reply_wav_bytes": len(speech.content),
                "reply_sha256": hashlib.sha256(speech.content).hexdigest(),
                "hardware": "Automated recorded-file round trip; browser microphone/speaker interaction unverified.",
            }

        check("voice_same_chat_pipeline", voice)

        def video() -> dict:
            from app.media.runtime import DEPENDENCIES

            sys.path.insert(0, str(DEPENDENCIES))
            import cv2

            image = cv2.imread(str(ROOT / "data/demo/bearing_cc0.jpg"))
            image = cv2.resize(image, (320, 240))
            path = directory / "demo-clip-from-licensed-still.mp4"
            writer = cv2.VideoWriter(
                str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240)
            )
            assert writer.isOpened()
            for _ in range(20):
                writer.write(image)
            writer.release()
            cid = conversation("bounded clip from licensed still, not real motion")
            uploaded = upload(cid, path.name, path.read_bytes())
            assert uploaded["metadata"]["video"]["decoded_frames"] == 20
            value = chat(
                cid,
                "Describe visible features in the sampled frames. This demonstration clip was encoded from a licensed still photograph, so it contains no evidence of real mechanical motion or failure.",
                [uploaded["id"]],
            )
            assert "hypotheses.investigate" not in [
                step["tool_id"] for step in value["trace"]["steps"]
            ], "Description request incorrectly routed to fault investigation"
            visual = [
                item
                for item in value["metadata"]["evidence"]
                if item["modality"] == "video_frame"
            ]
            assert visual and any(
                "decoder time" in (item.get("locator") or "") for item in visual
            )
            return {
                "source_kind": "Clearly labeled encoded demonstration from licensed still, not a physical incident video.",
                "decoded_metadata": uploaded["metadata"]["video"],
                "chat": value,
            }

        check("bounded_video_actual_frames_and_vision", video)

        result["voice_capabilities"] = (
            client.get("/api/v1/voice/capabilities").raise_for_status().json()
        )
        result["status"] = (
            "PASS for executed API/model/media checks"
            if all(value["status"] == "PASS" for value in result["checks"].values())
            else "INCOMPLETE; actual failures retained"
        )
        save()
        print(result["status"], flush=True)
    if result["status"].startswith("INCOMPLETE"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
