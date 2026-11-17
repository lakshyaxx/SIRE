"""Actual Silero/Whisper file transport and padding/source boundaries; physical mic remains unverified."""

import asyncio
import base64
import wave
import pytest
from starlette.websockets import WebSocketDisconnect
from app.media.runtime import MODELS, DEPENDENCIES
from app.voice.vad_process import VadProcess

AVAILABLE = (MODELS / "silero-vad/silero_vad.onnx").is_file() and (
    DEPENDENCIES / "sherpa_onnx"
).is_dir()


@pytest.mark.skipif(
    not AVAILABLE, reason="Optional pinned Silero weights/runtime not installed"
)
def test_real_vad_segments_are_exact_original_pcm_without_flush_padding():
    with wave.open(str(MODELS / "whisper-tiny-en/0.wav"), "rb") as recording:
        assert recording.getframerate() == 16000
        raw = recording.readframes(recording.getnframes())

    async def run():
        worker = VadProcess()
        segments = []
        try:
            assert (await worker.start())["type"] == "ready"
            for offset in range(0, len(raw), 6144):
                result = await worker.call(
                    {
                        "op": "feed",
                        "pcm_base64": base64.b64encode(
                            raw[offset : offset + 6144]
                        ).decode(),
                    }
                )
                segments.extend(result["segments"])
            result = await worker.call({"op": "flush"})
            segments.extend(result["segments"])
            assert segments
            for segment in segments:
                start, end = segment["start_sample"], segment["end_sample"]
                assert 0 <= start < end <= len(raw) // 2
                assert (
                    base64.b64decode(segment["pcm_base64"]) == raw[start * 2 : end * 2]
                )
        finally:
            await worker.close()
        assert worker.process is None

    asyncio.run(run())


def test_voice_origin_and_conversation_boundaries(v2client):
    assert "closed" in v2client.get("/api/v1/voice/session-schema").json()["events"]
    cid = v2client.app.state.store.create_conversation()["id"]
    with pytest.raises(WebSocketDisconnect) as blocked:
        with v2client.websocket_connect(
            "/api/v1/voice/session?conversation_id=" + cid,
            headers={"origin": "https://untrusted.example"},
        ):
            pytest.fail("Untrusted origin was admitted")
    assert blocked.value.code == 1008
    with pytest.raises(WebSocketDisconnect):
        with v2client.websocket_connect(
            "/api/v1/voice/session?conversation_id=test-only-missing",
            headers={"origin": "http://testserver"},
        ):
            pytest.fail("Missing conversation was admitted")


@pytest.mark.skipif(
    not AVAILABLE, reason="Optional pinned Silero weights/runtime not installed"
)
def test_real_voice_file_session_stores_scoped_audio_and_final_transcript(v2client):
    store = v2client.app.state.store
    cid = store.create_conversation()["id"]
    with wave.open(str(MODELS / "whisper-tiny-en/0.wav"), "rb") as recording:
        raw = recording.readframes(recording.getnframes())
    with v2client.websocket_connect(
        "/api/v1/voice/session?conversation_id=" + cid,
        headers={"origin": "http://testserver"},
    ) as socket:
        ready = socket.receive_json()
        assert ready["type"] == "ready"
        for offset in range(0, len(raw), 6144):
            socket.send_bytes(raw[offset : offset + 6144])
        socket.send_json({"op": "flush"})
        transcript = None
        for _ in range(12):
            event = socket.receive_json()
            assert event["type"] != "error", event
            if event["type"] == "transcript":
                transcript = event
                break
        assert (
            transcript
            and transcript["text"].strip()
            and transcript["model"] == "whisper-tiny.en-int8"
        )
        item = store.attachment(transcript["attachment_id"], cid)
        assert item["metadata"]["transcript"]["text"] == transcript["text"]
        with wave.open(item["path"], "rb") as recording:
            assert 0 < recording.getnframes() / recording.getframerate() <= 6.625
        socket.send_json({"op": "close"})
        assert socket.receive_json()["type"] == "closed"
    assert not v2client.app.state.voice_sessions
    session = store.rows(
        "SELECT * FROM v45_voice_sessions WHERE conversation_id=?", (cid,)
    )[0]
    assert session["status"] == "stopped"
    assert not store.messages(
        cid
    )  # ASR is real evidence, not a fabricated assistant answer.
