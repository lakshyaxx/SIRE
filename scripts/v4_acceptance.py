"""Focused real loopback acceptance; never writes production or frozen stress outputs."""

import argparse
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
    """Persist actual responses and timings, including explicit failures and limitations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--media", action="store_true")
    parser.add_argument("--prediction", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / ".runtime/v4").resolve()):
        raise SystemExit("Output must stay in the disposable V4 namespace")
    output.mkdir(exist_ok=False, parents=True)
    source = json.loads(args.proof.read_text(encoding="utf-8"))
    cid = source["conversationId"]
    results = {
        "scope": "Real HTTP, services and bytes; no browser/hardware acceptance",
        "checks": [],
    }
    with httpx.Client(
        base_url="http://127.0.0.1:8001/api/v1", timeout=310, trust_env=False
    ) as client:

        def record(name, operation):
            began = time.monotonic()
            try:
                evidence = operation()
                value = {"name": name, "status": "pass", "evidence": evidence}
            except Exception as exc:
                value = {
                    "name": name,
                    "status": "fail",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            value["elapsed_seconds"] = time.monotonic() - began
            results["checks"].append(value)
            (output / "results.json").write_text(
                json.dumps(results, indent=2), encoding="utf-8"
            )
            print(
                json.dumps(
                    {key: value[key] for key in ["name", "status", "elapsed_seconds"]}
                ),
                flush=True,
            )

        def json_get(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        def turn(question, ids):
            response = client.post(
                "/chat/message",
                json={
                    "conversation_id": cid,
                    "content": question,
                    "attachment_ids": ids,
                },
            )
            response.raise_for_status()
            events = [
                json.loads(line[6:])
                for line in response.text.splitlines()
                if line.startswith("data: ")
            ]
            assert events[-1]["status"] == "complete", events[-1]
            return {
                "events": events,
                "trace": json_get(
                    "/runs/"
                    + events[-1]["metadata"]["orchestration"]["run_id"]
                    + "/trace"
                ),
            }

        record("runtime_health", lambda: json_get("/health"))
        for uploaded in source["uploads"]:
            item = uploaded["receipt"]
            if item["kind"] != "document":
                continue

            def document(item=item):
                evidence = turn(
                    "According to this document, quote the actual record passages with source locators.",
                    [item["id"]],
                )
                meta = evidence["events"][-1]["metadata"]
                assert meta["response_route"] == "exact_retrieved_document_passages"
                assert meta["model_activity"] == []
                assert meta["claim_verification"] and all(
                    v["status"] == "supported_contextually"
                    for v in meta["claim_verification"]
                )
                for entry in meta["evidence"]:
                    resolved = json_get("/evidence/" + entry["id"])
                    observation = resolved["evidence"]["observation"]
                    assert entry["observation"] in observation.get(
                        "text", observation.get("excerpt", "")
                    )
                if item["mime"] == "application/pdf":
                    response = client.get("/attachments/" + item["id"] + "/content")
                    assert (
                        response.content.startswith(b"%PDF-")
                        and "application/pdf" in response.headers["content-type"]
                    )
                return evidence

            record("document_usage_" + item["name"], document)

        def invalid_files():
            cases = [
                ("empty.txt", b"", 413),
                ("bad.png", b"not an image", 422),
                ("bad.csv", b"a,b\n1,2,3\n", 422),
                ("bad.pdf", b"not a PDF", 422),
                ("bad.exe", b"MZ untrusted test fixture", 422),
            ]
            evidence = []
            for name, content, expected in cases:
                response = client.post(
                    "/attachments",
                    data={"conversation_id": cid},
                    files={"file": (name, content)},
                )
                assert response.status_code == expected, (
                    name,
                    response.status_code,
                    response.text,
                )
                evidence.append(
                    {
                        "name": name,
                        "status": response.status_code,
                        "body": response.json(),
                    }
                )
            return evidence

        record("invalid_files_controlled", invalid_files)
        record("persisted_sources", lambda: json_get("/conversations/" + cid))

        if args.prediction:
            for dataset in ["FD001", "FD002", "FD003", "FD004"]:

                def predict(dataset=dataset):
                    entry = next(
                        row
                        for row in json_get("/predictions/models?dataset=" + dataset)[
                            "models"
                        ]
                        if row["default"]
                    )
                    response = client.post(
                        "/predictions/run",
                        json={
                            "dataset": dataset,
                            "model_id": entry["model_id"],
                            "asset_id": dataset + "-ENGINE-001",
                        },
                    )
                    response.raise_for_status()
                    return response.json()

                record("genuine_saved_sample_" + dataset, predict)

        if args.media:

            def speech():
                recording = ROOT / ".runtime/media_models/whisper-tiny-en/0.wav"
                response = client.post(
                    "/voice/transcribe",
                    files={
                        "file": (
                            "actual-vendor-speech.wav",
                            recording.read_bytes(),
                            "audio/wav",
                        )
                    },
                )
                response.raise_for_status()
                transcript = response.json()
                assert transcript["text"].strip()
                reply = turn(transcript["text"], [])
                text = " ".join(e.get("text", "") for e in reply["events"])[:200]
                synthesized = client.post("/voice/speak", json={"text": text})
                synthesized.raise_for_status()
                (output / "actual-reply.wav").write_bytes(synthesized.content)
                with wave.open(io.BytesIO(synthesized.content), "rb") as audio:
                    assert audio.getnframes() > 0
                    audio_proof = {
                        "frames": audio.getnframes(),
                        "sample_rate": audio.getframerate(),
                        "seconds": audio.getnframes() / audio.getframerate(),
                    }
                return {
                    "input_sha256": hashlib.sha256(recording.read_bytes()).hexdigest(),
                    "transcript": transcript,
                    "chat": reply,
                    "wav": audio_proof,
                    "model": synthesized.headers["X-Speech-Model"],
                    "physical_microphone_speaker": "unverified",
                }

            record("actual_speech_chat_speech", speech)


if __name__ == "__main__":
    main()
