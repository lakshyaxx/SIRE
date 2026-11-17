"""Honest local voice/video readiness and bounded PCM inspection; no hosted speech fallback."""

import io
import shutil
import wave
from app.core.errors import SireError


def capabilities() -> dict:
    """Do not confuse a package import with installed weights or functioning transcription."""
    from app.media.runtime import DEPENDENCIES, readiness

    return {
        **readiness(),
        "asr_package_present": (DEPENDENCIES / "sherpa_onnx").is_dir(),
        "piper_package_present": False,
        "ffmpeg_present": shutil.which("ffmpeg") is not None,
    }


def inspect_wav(content: bytes) -> dict:
    """Validate real PCM audio structure/duration while refusing invented transcripts."""
    try:
        with wave.open(io.BytesIO(content), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
            if (
                duration > 60
                or not 8000 <= audio.getframerate() <= 192000
                or duration <= 0
                or audio.getnchannels() > 2
                or audio.getsampwidth() > 4
            ):
                raise ValueError("PCM limits")
            expected = audio.getnframes() * audio.getnchannels() * audio.getsampwidth()
            if len(audio.readframes(audio.getnframes())) != expected:
                raise ValueError("Truncated PCM data")
            return {
                "duration_seconds": duration,
                "sample_rate": audio.getframerate(),
                "channels": audio.getnchannels(),
                "transcription_status": "not_requested",
                "reason": capabilities()["reason"],
            }
    except (wave.Error, EOFError, ValueError, ZeroDivisionError) as exc:
        raise SireError(
            "invalid_audio", "Use valid PCM WAV of at most 60 seconds."
        ) from exc
