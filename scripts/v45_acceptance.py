"""Bounded real V45 loopback acceptance, with explicit failures and no device acceptance claim."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import socket
import sys
import time
import uuid
import wave

import httpx
from wsproto import ConnectionType, WSConnection
from wsproto.events import (
    AcceptConnection,
    BytesMessage,
    CloseConnection,
    Ping,
    Request,
    TextMessage,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    """Run selected real interfaces, saving raw answers, source identities and measured durations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--voice", action="store_true")
    parser.add_argument("--prediction", action="store_true")
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--cancel", action="store_true")
    parser.add_argument("--video", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / ".runtime/v45").resolve()):
        raise SystemExit("Use a fresh disposable V45 output namespace")
    output.mkdir(parents=True, exist_ok=False)
    source = json.loads(args.proof.read_text(encoding="utf-8"))
    cid = source["conversationId"]
    results = {
        "scope": "Real loopback HTTP/WebSocket, local VAD/Whisper/Qwen/Kokoro/native inference; physical microphone, audible latency and browser interruption unverified",
        "conversation_id": cid,
        "checks": [],
    }
    with httpx.Client(
        base_url="http://127.0.0.1:8001/api/v1", timeout=310, trust_env=False
    ) as client:

        def save() -> None:
            (output / "results.json").write_text(
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

        def get(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        def post(path, body):
            response = client.post(path, json=body)
            response.raise_for_status()
            return response.json()

        def turn(question, ids=None, **extra):
            events = []
            began = time.monotonic()
            with client.stream(
                "POST",
                "/chat/message",
                json={
                    "conversation_id": cid,
                    "content": question,
                    "attachment_ids": ids or [],
                    "request_id": uuid.uuid4().hex,
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
            assert events[-1]["type"] == "done", events[-1]
            return {
                "events": events,
                "answer": "".join(
                    event.get("text", "")
                    for event in events
                    if event["type"] == "delta"
                ),
                "trace": get(
                    "/runs/"
                    + events[-1]["metadata"]["orchestration"]["run_id"]
                    + "/trace"
                ),
            }

        record("health", lambda: get("/health"))

        if args.negative:

            def negative():
                measurement = next(
                    t for t in source["turns"] if t["content"].startswith("Summarize")
                )
                groups = measurement["events"][-1]["metadata"]["measurement_profiles"][
                    0
                ]["groups"]
                group = groups[0]
                identifier = group["evidence_id"]
                resolved = get("/evidence/" + identifier)["evidence"]
                row = resolved["observation"]["rows"][0]
                good = {
                    "category": "direct_observation",
                    "source_ids": [identifier],
                    "value": row["value"],
                    "unit": row["unit"],
                    "observed_at": row["observed_at"],
                    "asset_id": row["asset_id"],
                    "channel": row["channel"],
                }
                claims = [
                    good,
                    {**good, "value": good["value"] + 1.0},
                    {**good, "unit": "INTENTIONALLY_WRONG_TEST_UNIT"},
                    {**good, "asset_id": "UNRELATED-TEST-ASSET"},
                    {**good, "as_of": "1900-01-01T00:00:00Z"},
                ]
                checked = post(
                    "/evidence/verify", {"conversation_id": cid, "claims": claims}
                )
                statuses = [v["status"] for v in checked["verifications"]]
                assert statuses[0] == "verified_exact", checked
                assert statuses[1:3] == ["contradicted", "contradicted"], checked
                assert all(v != "verified_exact" for v in statuses[3:]), checked
                other = post("/conversations", {"title": "V45 isolation negative"})
                denied = client.post(
                    "/evidence/verify",
                    json={"conversation_id": other["id"], "claims": [good]},
                )
                assert denied.status_code == 404, denied.text
                return {
                    "original_evidence_id": identifier,
                    "exact_source_row": row,
                    "claims": claims,
                    "result": checked,
                    "cross_conversation_status": denied.status_code,
                }

            record(
                "actual_citation_value_unit_asset_future_negative_controls", negative
            )

        if args.prediction:
            for dataset in ("FD001", "FD002", "FD003", "FD004"):
                models = get("/predictions/models?dataset=" + dataset)["models"]
                selected = [
                    model
                    for model in models
                    if model.get("production_role")
                    in {"low_latency", "advanced", "deep"}
                ]
                for model in selected:

                    def prediction(dataset=dataset, model=model):
                        result = post(
                            "/predictions/run",
                            {
                                "dataset": dataset,
                                "model_id": model["model_id"],
                                "asset_id": dataset + "-ENGINE-001",
                            },
                        )
                        assert result["dataset"] == dataset
                        assert result["model_id"] == model["model_id"]
                        assert result["rul_cycles"] is not None
                        return {"role": model["production_role"], "result": result}

                    record(
                        "genuine_saved_" + dataset + "_" + model["production_role"],
                        prediction,
                    )

        if args.video:

            def video():
                path = args.video.resolve()
                if "SIRE_STRESS_LAB_PUBLIC" not in path.parts:
                    raise ValueError(
                        "Only the public corpus may enter the test runtime"
                    )
                data = path.read_bytes()
                response = client.post(
                    "/attachments",
                    data={"conversation_id": cid},
                    files={"file": (path.name, data, "video/mp4")},
                )
                response.raise_for_status()
                receipt = response.json()
                frames = receipt["metadata"].get("video", {}).get("frames", [])
                assert frames and not receipt["metadata"].get("media_error"), receipt
                for frame in frames:
                    response = client.get(
                        "/attachments/" + frame["attachment_id"] + "/content"
                    )
                    response.raise_for_status()
                    assert (
                        hashlib.sha256(response.content).hexdigest() == frame["sha256"]
                    )
                return {
                    "fixture": str(path),
                    "original_sha256": hashlib.sha256(data).hexdigest(),
                    "receipt": receipt,
                    "scope": "Actual bounded frame extraction and immutable frame bytes; motion/cause inference not asserted",
                }

            record("real_video_frame_extraction", video)

        if args.voice:

            def voice():
                recording = ROOT / ".runtime/media_models/whisper-tiny-en/0.wav"
                with wave.open(str(recording), "rb") as audio:
                    assert (
                        audio.getnchannels(),
                        audio.getsampwidth(),
                        audio.getframerate(),
                    ) == (
                        1,
                        2,
                        16000,
                    )
                    raw = audio.readframes(audio.getnframes())
                protocol = WSConnection(ConnectionType.CLIENT)
                events = []
                began = time.monotonic()
                with socket.create_connection(
                    ("127.0.0.1", 8001), timeout=130
                ) as connection:
                    connection.sendall(
                        protocol.send(
                            Request(
                                host="127.0.0.1:8001",
                                target="/api/v1/voice/session?conversation_id=" + cid,
                                extra_headers=[(b"origin", b"http://127.0.0.1:8001")],
                            )
                        )
                    )
                    pending = []
                    text = ""

                    def receive():
                        nonlocal text
                        while not pending:
                            received = connection.recv(65536)
                            if not received:
                                raise RuntimeError(
                                    "Voice connection ended without acknowledgement"
                                )
                            protocol.receive_data(received)
                            for event in protocol.events():
                                if isinstance(event, Ping):
                                    connection.sendall(protocol.send(event.response()))
                                elif isinstance(event, TextMessage):
                                    text += event.data
                                    if event.message_finished:
                                        pending.append(json.loads(text))
                                        text = ""
                                elif isinstance(event, CloseConnection):
                                    if not pending:
                                        raise RuntimeError(
                                            f"Voice closed early code={event.code}"
                                        )
                                elif not isinstance(event, AcceptConnection):
                                    raise RuntimeError(
                                        f"Unexpected voice handshake event {event!r}"
                                    )
                        value = pending.pop(0)
                        events.append(
                            {**value, "received_seconds": time.monotonic() - began}
                        )
                        return value

                    assert receive()["type"] == "ready"
                    for offset in range(0, len(raw), 6144):
                        connection.sendall(
                            protocol.send(
                                BytesMessage(data=raw[offset : offset + 6144])
                            )
                        )
                    connection.sendall(
                        protocol.send(TextMessage(data='{"op":"flush"}'))
                    )
                    transcript = None
                    for _ in range(15):
                        event = receive()
                        assert event["type"] != "error", event
                        if event["type"] == "transcript":
                            transcript = event
                            break
                    assert transcript and transcript["text"].strip(), events
                    connection.sendall(
                        protocol.send(TextMessage(data='{"op":"close"}'))
                    )
                    assert receive()["type"] == "closed"
                asr_seconds = time.monotonic() - began
                response = turn(
                    transcript["text"],
                    [transcript["attachment_id"]],
                    voice_response=True,
                )
                assert response["events"][-1]["status"] == "complete", response
                text = response["answer"].strip()
                assert text
                tts_began = time.monotonic()
                with client.stream(
                    "POST",
                    "/voice/speak",
                    json={"text": text[:240], "request_id": uuid.uuid4().hex},
                ) as speech:
                    speech.raise_for_status()
                    parts = []
                    first_byte = None
                    for data in speech.iter_bytes():
                        if first_byte is None:
                            first_byte = time.monotonic() - tts_began
                        parts.append(data)
                    model = speech.headers["x-speech-model"]
                content = b"".join(parts)
                (output / "actual-voice-reply.wav").write_bytes(content)
                with wave.open(io.BytesIO(content), "rb") as audio:
                    assert audio.getnframes() > 0
                    wav = {
                        "frames": audio.getnframes(),
                        "sample_rate": audio.getframerate(),
                    }
                return {
                    "input_sha256": hashlib.sha256(recording.read_bytes()).hexdigest(),
                    "input_seconds": len(raw) / 32000,
                    "file_feed": "Back-to-back actual file PCM, not real-time microphone pacing",
                    "events": events,
                    "asr_session_seconds": asr_seconds,
                    "chat": response,
                    "tts_model": model,
                    "tts_first_network_bytes_seconds": first_byte,
                    "tts_total_seconds": time.monotonic() - tts_began,
                    "speech_text": text[:240],
                    "wav": wav,
                    "total_seconds": time.monotonic() - began,
                    "first_audible_seconds": None,
                }

            record("actual_network_VAD_ASR_chat_TTS", voice)

        if args.cancel:

            def cancel():
                images = [
                    upload["receipt"]["id"]
                    for upload in source["uploads"]
                    if upload["receipt"]["kind"] == "image"
                ]
                accepted = post(
                    "/investigation-jobs",
                    {
                        "conversation_id": cid,
                        "content": "Compare competing explanations for this schematic; treat it as a drawing, not physical confirmation.",
                        "attachment_ids": images,
                        "mode": "investigate",
                        "request_id": uuid.uuid4().hex,
                    },
                )
                began = time.monotonic()
                before = None
                while time.monotonic() - began < 35:
                    before = get("/runtime/resources")
                    if before["scheduler"]["active"]:
                        break
                    time.sleep(0.1)
                assert before["scheduler"][
                    "active"
                ], "No actual heavy-model operation observed"
                stopped = post(
                    "/investigation-jobs/"
                    + accepted["id"]
                    + "/cancel?conversation_id="
                    + cid,
                    {},
                )
                deadline = time.monotonic() + 10
                while True:
                    after = get("/runtime/resources")
                    if not after["scheduler"]["active"] or time.monotonic() >= deadline:
                        break
                    time.sleep(0.1)
                final = get(
                    "/investigation-jobs/" + accepted["id"] + "?conversation_id=" + cid
                )
                assert stopped["status"] == final["status"] == "cancelled", final
                assert not after["scheduler"]["active"], after
                return {
                    "accepted": accepted,
                    "before": before,
                    "final": final,
                    "after": after,
                }

            record("cancel_real_heavy_job_releases_scheduler", cancel)
        results["resources_after"] = get("/runtime/resources")
        save()


if __name__ == "__main__":
    main()
