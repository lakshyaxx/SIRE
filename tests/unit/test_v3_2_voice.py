"""Local speech contracts, genuine optional model round trip and bounded failure behavior."""

import io
import threading
import time
import wave
import pytest
from app.core.errors import SireError
from app.media import runtime
from app.voice.text import number_words, spoken_text


@pytest.mark.parametrize(
    "value,words",
    [
        ("114.496", "one hundred fourteen point four nine six"),
        ("-20", "minus twenty"),
        ("1000", "one thousand"),
        ("0.01", "zero point zero one"),
    ],
)
def test_spoken_exact_digits(value, words):
    assert number_words(value) == words


def test_lexicon_fallback_and_unsupported_language(tmp_path):
    dictionary = tmp_path / "test-only-lexicon.txt"
    dictionary.write_text(
        "one w\npoint p\nfive f\ncycles s\na a\nb b\nc c\n", encoding="utf-8"
    )
    text, warnings = spoken_text("1.5 cycles abc [EV:1234567890abcdef]", dictionary)
    assert text == "one point five cycles a b c" and warnings
    with pytest.raises(SireError, match="English"):
        spoken_text("one 中文", dictionary)


def test_legacy_transcript_and_document_citations_are_not_spelled_as_speech(tmp_path):
    dictionary = tmp_path / "test-only-lexicon.txt"
    dictionary.write_text("one w\npoint p\nfive f\ncycles c\n", encoding="utf-8")
    text, warnings = spoken_text(
        "1.5 cycles [ccf5de4a66554346bdbe2d8cb4d4dcb0:transcript] [abcdefabcdefabcdefabcdef]",
        dictionary,
    )
    assert text == "one point five cycles" and not warnings


def test_missing_optional_weights_fail_without_substitution(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "MODELS", tmp_path)
    with pytest.raises(SireError, match="provision"):
        runtime.model_files("asr")
    assert not runtime.readiness()["asr_ready"]


def optional_models() -> bool:
    try:
        runtime.model_files("asr", False)
        runtime.model_files("tts", False)
        return (runtime.DEPENDENCIES / "sherpa_onnx").is_dir()
    except SireError:
        return False


@pytest.mark.skipif(
    not optional_models(),
    reason="Optional isolated local speech runtime/weights not provisioned",
)
def test_real_local_synthesis_transcription_roundtrip(v2client):
    response = v2client.post(
        "/api/v1/voice/speak",
        json={
            "text": "This is a simulated investigation. Independent inspection is required."
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["X-Speech-Model"] == "kokoro-en-v0.19-int8"
    with wave.open(io.BytesIO(response.content), "rb") as recording:
        assert recording.getnframes() == int(response.headers["X-Audio-Frames"])
        assert 0 < recording.getnframes() / recording.getframerate() <= 60
    recognized = v2client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("actual-generated.wav", response.content, "audio/wav")},
    )
    assert recognized.status_code == 200, recognized.text
    result = recognized.json()
    assert (
        "simulated" in result["text"].casefold()
        and "inspection" in result["text"].casefold()
    )
    assert result["alignment"].startswith("whole_recording_window_only")
    assert runtime.readiness()["asr_ready"] and runtime.readiness()["tts_ready"]


@pytest.mark.skipif(
    not optional_models(),
    reason="Optional isolated local speech runtime/weights not provisioned",
)
def test_real_media_cancellation_releases_model_budget():
    errors = []

    def work():
        try:
            runtime.run(
                "tts",
                {"text": "This is a longer simulated investigation. " * 20},
                "test-only-cancel",
            )
        except SireError as exc:
            errors.append(exc.code)

    thread = threading.Thread(target=work)
    thread.start()
    deadline = time.monotonic() + 10
    while "test-only-cancel" not in runtime.JOBS and time.monotonic() < deadline:
        time.sleep(0.02)
    assert runtime.cancel("test-only-cancel")
    thread.join(timeout=10)
    assert not thread.is_alive() and errors == ["media_cancelled"]
    assert not runtime.JOBS
    assert runtime.INFERENCE_LOCK.acquire(blocking=False)
    runtime.INFERENCE_LOCK.release()
