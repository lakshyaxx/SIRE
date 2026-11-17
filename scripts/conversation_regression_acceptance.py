"""Real loopback conversation/voice acceptance with explicit browser and noise limitations."""

import argparse
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import threading
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


class VoiceSocket:
    """Actual wsproto/TCP client; PCM is a real recorded file, not a fake transcript response."""

    def __init__(self, cid: str):
        self.protocol = WSConnection(ConnectionType.CLIENT)
        self.socket = socket.create_connection(("127.0.0.1", 8001), timeout=30)
        self.pending: list[dict] = []
        self.partial = ""
        self.events: list[dict] = []
        self.started = time.monotonic()
        self.socket.sendall(
            self.protocol.send(
                Request(
                    host="127.0.0.1:8001",
                    target="/api/v1/voice/session?conversation_id=" + cid,
                    extra_headers=[(b"origin", b"http://127.0.0.1:8001")],
                )
            )
        )
        assert self.receive()["type"] == "ready"

    def receive(self) -> dict:
        """Receive actual final events, preserving elapsed times and refusing early close."""
        while not self.pending:
            data = self.socket.recv(65536)
            if not data:
                raise RuntimeError("Voice socket closed without acknowledgement")
            self.protocol.receive_data(data)
            for event in self.protocol.events():
                if isinstance(event, Ping):
                    self.socket.sendall(self.protocol.send(event.response()))
                elif isinstance(event, TextMessage):
                    self.partial += event.data
                    if event.message_finished:
                        self.pending.append(json.loads(self.partial))
                        self.partial = ""
                elif isinstance(event, CloseConnection) and not self.pending:
                    raise RuntimeError(f"Voice closed early: {event.code}")
                elif not isinstance(event, (CloseConnection, AcceptConnection)):
                    raise RuntimeError(f"Unexpected event: {event!r}")
        value = self.pending.pop(0)
        self.events.append(
            {**value, "received_seconds": time.monotonic() - self.started}
        )
        return value

    def control(self, value: dict) -> None:
        """Send an actual protocol control."""
        self.socket.sendall(self.protocol.send(TextMessage(data=json.dumps(value))))

    def feed(self, path: Path) -> None:
        """Replay exact original PCM; no microphone pacing or physical acquisition is claimed."""
        with wave.open(str(path), "rb") as recording:
            assert (
                recording.getframerate(),
                recording.getnchannels(),
                recording.getsampwidth(),
            ) == (16000, 1, 2)
            raw = recording.readframes(recording.getnframes())
        for offset in range(0, len(raw), 6144):
            self.socket.sendall(
                self.protocol.send(BytesMessage(data=raw[offset : offset + 6144]))
            )
        self.control({"op": "flush"})

    def close(self) -> None:
        """Close and require the actual server cleanup acknowledgement."""
        try:
            self.socket.settimeout(5)
            self.control({"op": "close"})
            while self.receive()["type"] != "closed":
                continue
        finally:
            self.socket.close()


def main() -> None:
    """Execute real local services and retain unconfirmed physical tests as unconfirmed."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / ".runtime/v45_conversation").resolve()):
        raise SystemExit(
            "Use a fresh disposable conversation regression output directory"
        )
    output.mkdir(parents=True, exist_ok=False)
    results = {
        "scope": "Actual loopback HTTP/WebSocket, original recorded speech, local ASR/models. Physical browser microphone/speaker/noise/barge-in unverified.",
        "cases": [],
    }
    with httpx.Client(
        base_url="http://127.0.0.1:8001/api/v1", timeout=180, trust_env=False
    ) as client:
        cid = client.post(
            "/conversations",
            json={"title": "Disposable conversation regression acceptance"},
        ).json()["id"]
        results["conversation_id"] = cid

        def save() -> None:
            (output / "results.json").write_text(
                json.dumps(results, indent=2), encoding="utf-8"
            )

        def turn(question: str, attachments=None, started=None, **extra) -> dict:
            began = time.monotonic()
            events = []
            with client.stream(
                "POST",
                "/chat/message",
                json={
                    "conversation_id": cid,
                    "content": question,
                    "attachment_ids": attachments or [],
                    "request_id": extra.pop("request_id", uuid.uuid4().hex),
                    "background_if_deep": True,
                    **extra,
                },
            ) as response:
                response.raise_for_status()
                assert response.status_code == 200
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        event = json.loads(line[6:])
                        events.append(
                            {**event, "received_seconds": time.monotonic() - began}
                        )
                        if event["type"] == "started" and started:
                            started.set()
            assert events and events[-1]["type"] == "done", events
            meta = events[-1]["metadata"]
            trace = client.get(
                "/runs/" + meta["orchestration"]["run_id"] + "/trace"
            ).json()
            return {
                "question": question,
                "status": events[-1]["status"],
                "route": meta["orchestration"]["intent"],
                "response_route": meta.get("response_route"),
                "evidence_schema": "EvidenceItem[]",
                "validation_profile": meta.get("validation_profile"),
                "first_text_seconds": next(
                    (e["received_seconds"] for e in events if e["type"] == "delta"),
                    None,
                ),
                "total_seconds": time.monotonic() - began,
                "answer": "".join(
                    e.get("text", "") for e in events if e["type"] == "delta"
                ),
                "events": events,
                "trace": trace,
                "unwanted_model_tool_calls": [
                    s["tool_id"]
                    for s in trace["steps"]
                    if (
                        meta.get("response_route") == "fast_conversation"
                        and s["tool_id"]
                        in {
                            "llm.chat",
                            "hypotheses.investigate",
                            "knowledge.retrieve",
                            "vision.inspect",
                        }
                    )
                    or (
                        not attachments
                        and s["tool_id"]
                        in {
                            "hypotheses.investigate",
                            "vision.inspect",
                            "prediction.run",
                        }
                    )
                ],
            }

        def record(name, operation, expected="complete") -> None:
            began = time.monotonic()
            try:
                value = operation()
                if expected is not None:
                    assert value["status"] == expected, value
                row = {"test": name, "status": "pass", "actual": value}
            except Exception as exc:
                row = {
                    "test": name,
                    "status": "fail",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            row["elapsed_seconds"] = time.monotonic() - began
            results["cases"].append(row)
            save()
            print(
                json.dumps(
                    {
                        "test": name,
                        "status": row["status"],
                        "seconds": row["elapsed_seconds"],
                    }
                ),
                flush=True,
            )

        for name, question in [
            ("1_new_hi", "hi"),
            ("2_existing_hi", "hi"),
            ("3_what_is_SIRE", "What is SIRE?"),
            ("4_hypothesis_engine", "How does your hypothesis engine work?"),
        ]:
            record(name, lambda question=question: turn(question))

        snapshot = ROOT / ".runtime/v45_conversation/production_before.sqlite3"
        with sqlite3.connect(snapshot.as_uri() + "?mode=ro", uri=True) as db:
            speech = []
            for question in [
                "Hello?",
                "I want to talk to you, give me some answers, bro.",
            ]:
                row = db.execute(
                    "SELECT metadata FROM messages WHERE role='user' AND content=? ORDER BY created_at DESC LIMIT 1",
                    (question,),
                ).fetchone()
                identifier = json.loads(row[0])["attachments"][0]
                raw = db.execute(
                    "SELECT path FROM attachments WHERE id=?", (identifier,)
                ).fetchone()[0]
                speech.append(Path(raw))

        def voice(path: Path) -> dict:
            began = time.monotonic()
            socket_client = VoiceSocket(cid)
            try:
                socket_client.feed(path)
                transcript = None
                for _ in range(10):
                    event = socket_client.receive()
                    assert event["type"] != "error", event
                    if event["type"] == "transcript":
                        transcript = event
                        break
                assert transcript, socket_client.events
                socket_client.close()
                result = turn(
                    transcript["text"],
                    [transcript["attachment_id"]],
                    input_audio_id=transcript["attachment_id"],
                    voice_response=True,
                )
                result.update(
                    voice_events=socket_client.events,
                    original_audio_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    transcript=transcript,
                    speech_input_total_seconds=time.monotonic() - began,
                )
                assert (
                    result["route"] == "fast_conversation"
                    and not result["unwanted_model_tool_calls"]
                )
                return result
            except BaseException:
                socket_client.socket.close()
                raise

        record("5_voice_Hello_recorded_file", lambda: voice(speech[0]))
        record(
            "6_voice_followup_after_text",
            lambda: (turn("What is SIRE?"), voice(speech[1]))[1],
        )
        record(
            "7_text_after_voice",
            lambda: turn("Can you explain to me what SIRE is all about?"),
        )

        def interruption() -> dict:
            signal = threading.Event()
            values = []
            errors = []
            rid = uuid.uuid4().hex

            def work():
                try:
                    values.append(
                        turn(
                            "Tell me a short story about a train.",
                            started=signal,
                            request_id=rid,
                        )
                    )
                except Exception as exc:
                    errors.append(repr(exc))

            worker = threading.Thread(target=work)
            worker.start()
            assert signal.wait(10)
            began = time.monotonic()
            response = client.post(
                "/chat/cancel",
                json={"request_id": rid, "reason": "voice_user_interrupt"},
            )
            response.raise_for_status()
            worker.join(10)
            assert not worker.is_alive() and not errors and values, errors
            value = values[0]
            assert value["status"] == "cancelled", value
            assert (
                value["events"][-1]["metadata"]["cancellation"]["reason"]
                == "voice_user_interrupt"
            )
            value.update(
                cancel_seconds=time.monotonic() - began,
                cancellation=response.json(),
                physical_browser_barge_in="unverified; actual explicit network control and client policy tested separately",
            )
            return value

        record("8_deliberate_interrupt_network_control", interruption, "cancelled")

        def silence() -> dict:
            path = args.corpus / "media/audio/silence_2s.wav"
            socket_client = VoiceSocket(cid)
            try:
                socket_client.feed(path)
                socket_client.socket.settimeout(2)
                try:
                    while True:
                        assert (
                            socket_client.receive()["type"] != "transcript"
                        ), socket_client.events
                except TimeoutError:
                    pass
                socket_client.close()
                return {
                    "status": "quiet_control_pass_background_noise_unverified",
                    "route": "voice_VAD_only",
                    "evidence_schema": "No speech evidence generated",
                    "first_text_seconds": None,
                    "total_seconds": time.monotonic() - socket_client.started,
                    "events": socket_client.events,
                    "unwanted_model_tool_calls": [],
                    "limitation": "The supplied fixture is digital silence. A labeled noise-only recording and physical background-noise acceptance are unavailable; not counted as a noise pass.",
                }
            finally:
                socket_client.socket.close()

        record(
            "9_no_speech_control",
            silence,
            "quiet_control_pass_background_noise_unverified",
        )

        def industrial() -> dict:
            path = args.corpus / "test_inputs/valid/telemetry_small.csv"
            response = client.post(
                "/attachments",
                data={"conversation_id": cid},
                files={"file": (path.name, path.read_bytes(), "text/csv")},
            )
            response.raise_for_status()
            value = turn(
                "Summarize exact descriptive sensor statistics and units from this uploaded CSV, citing actual evidence. These are synthetic measurements, not NASA inputs.",
                [response.json()["id"]],
            )
            meta = value["events"][-1]["metadata"]
            assert meta["claim_verification"] and all(
                c["status"] == "verified_exact" for c in meta["claim_verification"]
            )
            assert meta["evidence"] and "EV:" in value["answer"]
            return value

        record("10_industrial_source_backed_statistics", industrial)
        record(
            "11_plain_model_unseen_question",
            lambda: turn("Tell me a short joke about trains."),
        )
        record(
            "12_engineering_general_concept",
            lambda: turn(
                "In two short sentences, explain how rolling bearings reduce friction. No machine-specific measurements are supplied."
            ),
        )
        results["resources_after"] = client.get("/runtime/resources").json()
        save()


if __name__ == "__main__":
    main()
