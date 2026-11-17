"""Fixed local CPU operations; third-party speech/codec imports stay outside the API process."""

import io
import json
from pathlib import Path
import sys
import wave
import time
from app.media.runtime import DEPENDENCIES, MODELS, POLICY, model_files
from app.core.errors import SireError


def pcm(content: bytes) -> tuple[int, object, float]:
    """Decode real bounded integer PCM, preserving the actual sample rate and duration."""
    import numpy as np
    from app.voice.capabilities import inspect_wav

    metadata = inspect_wav(content)
    with wave.open(io.BytesIO(content), "rb") as audio:
        width = audio.getsampwidth()
        raw = audio.readframes(audio.getnframes())
        if width == 1:
            samples = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
        elif width == 3:
            data = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
            values = data[:, 0] | data[:, 1] << 8 | data[:, 2] << 16
            samples = ((values ^ 0x800000) - 0x800000).astype(np.float32) / 8388608
        else:
            samples = np.frombuffer(raw, dtype="<i2" if width == 2 else "<i4").astype(
                np.float32
            ) / (32768 if width == 2 else 2147483648)
        if audio.getnchannels() == 2:
            samples = samples.reshape(-1, 2).mean(axis=1)
        return audio.getframerate(), samples, metadata["duration_seconds"]


def transcribe(path: Path) -> dict:
    """Return actual English Whisper output; no guessed token/word alignment timestamps."""
    import sherpa_onnx

    paths = model_files("asr")
    format_metadata = {"container": "PCM WAV"}
    if path.suffix.lower() == ".wav":
        rate, samples, duration = pcm(path.read_bytes())
    else:
        import soundfile as sf

        try:
            with sf.SoundFile(str(path)) as audio:
                rate = audio.samplerate
                if (
                    not 8000 <= rate <= 192000
                    or not 1 <= audio.channels <= 2
                    or not 0 < audio.frames <= rate * POLICY["max_audio_seconds"]
                ):
                    raise SireError(
                        "audio_limits",
                        "Audio exceeds the sample-rate, channel or 60-second limit.",
                        413,
                    )
                samples = audio.read(dtype="float32", always_2d=True).mean(axis=1)
                duration = len(samples) / rate
                format_metadata = {
                    "container": audio.format,
                    "codec_subtype": audio.subtype,
                    "decoder": "libsndfile",
                }
        except (ValueError, RuntimeError) as exc:
            raise SireError(
                "invalid_audio",
                "Local decoder could not read this bounded audio file.",
                422,
            ) from exc
    import numpy as np

    if not np.isfinite(samples).all():
        raise SireError("invalid_audio", "Audio contains non-finite samples.", 422)

    if float(np.sqrt(np.mean(samples * samples))) < 0.0001:
        raise SireError(
            "no_speech_input",
            "Recording is silent or below the configured usable signal level. Type or record again.",
            422,
        )
    recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=str(paths["tiny.en-encoder.int8.onnx"]),
        decoder=str(paths["tiny.en-decoder.int8.onnx"]),
        tokens=str(paths["tiny.en-tokens.txt"]),
        num_threads=POLICY["threads"],
        provider="cpu",
        language="en",
        task="transcribe",
    )
    stream = recognizer.create_stream()
    stream.accept_waveform(rate, samples)
    recognizer.decode_stream(stream)
    text = stream.result.text.strip()
    if not text:
        raise SireError(
            "no_speech_recognized",
            "The local model returned no speech. Review the recording or type the question.",
            422,
        )
    return {
        "text": text,
        "duration_seconds": duration,
        "sample_rate": rate,
        "format": format_metadata,
        "language": "en",
        "model": "whisper-tiny.en-int8",
        "provider": "sherpa-onnx-2.0.1",
        "source_type": "model_generated",
        "alignment": "whole_recording_window_only; word/segment alignment unavailable",
        "recording_window": {"start_seconds": 0, "end_seconds": duration},
        "limitations": [
            "Automatic transcription is unverified; review and edit before sending.",
            "English-only model; noise and technical terms can be misrecognized.",
        ],
        "model_hashes": POLICY["models"]["asr"]["files"],
    }


def synthesize(text: str, workspace: Path) -> dict:
    """Generate actual local WAV with a lexicon-only front end; no GPL phonemizer."""
    import numpy as np
    import sherpa_onnx
    from app.voice.text import spoken_text

    began = time.monotonic()
    paths = model_files("tts")
    normalized, warnings = spoken_text(text, paths["lexicon-en-us.txt"])
    config = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                model=str(paths["model.int8.onnx"]),
                voices=str(paths["voices.bin"]),
                tokens=str(paths["tokens.txt"]),
                lexicon=str(paths["lexicon-en-us.txt"]),
            ),
            num_threads=POLICY["tts_threads"],
            provider="cpu",
        ),
        max_num_sentences=1,
    )
    if not config.validate():
        raise SireError(
            "tts_configuration", "The local TTS configuration failed validation.", 503
        )
    initializing = time.monotonic()
    engine = sherpa_onnx.OfflineTts(config)
    generating = time.monotonic()
    speech = engine.generate(normalized, sid=0, speed=1.0)
    generated = time.monotonic()
    if not len(speech.samples) or not np.max(np.abs(speech.samples)):
        raise SireError("tts_empty", "Local TTS generated empty or silent audio.", 503)
    if len(speech.samples) / speech.sample_rate > POLICY["max_audio_seconds"]:
        raise SireError(
            "tts_audio_limit",
            "Choose a shorter text excerpt for bounded local speech.",
            422,
        )
    with wave.open(str(workspace / "speech.wav"), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(speech.sample_rate)
        audio.writeframes(
            (np.clip(speech.samples, -1, 1) * 32767).astype("<i2").tobytes()
        )
    return {
        "sample_rate": speech.sample_rate,
        "frames": len(speech.samples),
        "duration_seconds": len(speech.samples) / speech.sample_rate,
        "model": "kokoro-en-v0.19-int8",
        "provider": "sherpa-onnx-2.0.1",
        "spoken_text": normalized,
        "warnings": warnings,
        "source_type": "model_generated",
        "model_hashes": POLICY["models"]["tts"]["files"],
        "phase_timings": {
            "validation_normalization_seconds": initializing - began,
            "model_initialization_seconds": generating - initializing,
            "generation_seconds": generated - generating,
            "wav_write_seconds": time.monotonic() - generated,
        },
    }


def main() -> None:
    """Execute only one explicit operation, writing typed JSON and private output files."""
    sys.path.insert(0, str(DEPENDENCIES))
    request = json.load(sys.stdin)
    operation, payload = request["operation"], request["payload"]
    workspace = Path(request["workspace"])
    try:
        if operation == "asr":
            result = transcribe(Path(payload["path"]))
        elif operation == "tts":
            result = synthesize(payload["text"], workspace)
        elif operation == "video":
            from app.media.video import sample_frames

            result = sample_frames(Path(payload["path"]), workspace)
        else:
            raise ValueError("Unsupported operation")
        if operation in {"asr", "tts"}:
            import hashlib
            from app.storage.database import now

            proof_path = MODELS / "verified.json"
            proof = (
                json.loads(proof_path.read_text(encoding="utf-8"))
                if proof_path.is_file()
                else {}
            )
            proof[operation] = {
                "timestamp_utc": now(),
                "model_fingerprint": hashlib.sha256(
                    json.dumps(
                        POLICY["models"][operation]["files"], sort_keys=True
                    ).encode()
                ).hexdigest(),
                "model": result["model"],
            }
            temporary = proof_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(proof, indent=2), encoding="utf-8")
            temporary.replace(proof_path)
        if operation == "video":
            from app.storage.database import now

            proof_path = MODELS / "verified.json"
            proof = (
                json.loads(proof_path.read_text(encoding="utf-8"))
                if proof_path.is_file()
                else {}
            )
            proof["video"] = {
                "decoded_test": True,
                "timestamp_utc": now(),
                "codec": result["codec"],
            }
            temporary = proof_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(proof, indent=2), encoding="utf-8")
            temporary.replace(proof_path)
        print(json.dumps(result, allow_nan=False))
    except SireError as exc:
        print(
            json.dumps(
                {
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                        "status": exc.status,
                    }
                }
            )
        )


if __name__ == "__main__":
    main()
