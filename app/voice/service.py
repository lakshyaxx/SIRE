"""Actual bounded speech jobs; recordings remain local and automatic text is unverified."""

import hashlib
from threading import Event
from pathlib import Path
import tempfile
from app.core.config import ROOT
from app.media.runtime import run
from app.voice.capabilities import inspect_wav


def validate_audio(content: bytes, suffix: str) -> None:
    """Validate supported container signatures before invoking native decoders."""
    if suffix == ".wav":
        inspect_wav(content)
    elif not (
        (suffix == ".flac" and content.startswith(b"fLaC"))
        or (suffix == ".ogg" and content.startswith(b"OggS"))
        or (
            suffix == ".mp3"
            and (
                content.startswith(b"ID3")
                or (len(content) > 2 and content[0] == 255 and content[1] & 224 == 224)
            )
        )
    ):
        from app.core.errors import SireError

        raise SireError(
            "invalid_audio_container",
            "Use actual PCM WAV, FLAC, OGG or MP3 audio.",
            422,
        )


def transcribe_bytes(
    content: bytes,
    identifier: str | None = None,
    suffix: str = ".wav",
    cancel_event: Event | None = None,
) -> dict:
    """Transcribe real validated bytes without any hosted speech fallback."""
    validate_audio(content, suffix)
    directory = ROOT / ".runtime/media_inputs"
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        suffix=suffix, dir=directory, delete=False
    ) as source:
        path = Path(source.name).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Audio input leaves its private directory")
        source.write(content)
    try:
        result = run("asr", {"path": str(path)}, identifier, cancel_event=cancel_event)
        return {**result, "original_sha256": hashlib.sha256(content).hexdigest()}
    finally:
        path.unlink(missing_ok=True)
