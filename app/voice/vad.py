"""Real Silero streaming boundaries; sample clocks and padding never become physical timestamps."""

import base64
from pathlib import Path
from typing import Any
import yaml
from app.core.config import ROOT
from app.core.errors import SireError

POLICY = yaml.safe_load((ROOT / "config/voice.yaml").read_text(encoding="utf-8"))


class VadStream:
    """Run only inside the isolated media worker; bounded PCM16 mono at a declared16kHz."""

    def __init__(self, model: Path) -> None:
        import numpy as np
        import sherpa_onnx

        self.np = np
        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(model)
        config.silero_vad.threshold = POLICY["vad_threshold"]
        config.silero_vad.min_silence_duration = POLICY["min_silence_seconds"]
        config.silero_vad.min_speech_duration = POLICY["min_speech_seconds"]
        config.silero_vad.max_speech_duration = POLICY["max_speech_seconds"]
        config.sample_rate = POLICY["sample_rate"]
        config.num_threads = 1
        self.detector = sherpa_onnx.VoiceActivityDetector(
            config, buffer_size_in_seconds=60
        )
        self.pending = bytearray()
        self.received_samples = 0
        self.base_samples = 0
        self.speaking = False
        self.source_pcm = bytearray()
        self.source_base = 0
        self.last_segment_end = 0

    def _collect(self) -> list[dict]:
        segments = []
        while not self.detector.empty():
            front = self.detector.front
            detected_start = self.base_samples + front.start
            samples = self.np.array(front.samples, copy=True)
            raw_end = detected_start + len(samples)
            end = min(raw_end, self.received_samples)
            start = max(
                self.source_base,
                self.last_segment_end,
                detected_start
                - int(POLICY["pre_roll_seconds"] * POLICY["sample_rate"]),
            )
            pcm = bytes(
                self.source_pcm[
                    (start - self.source_base) * 2 : (end - self.source_base) * 2
                ]
            )
            if pcm:
                self.last_segment_end = end
                segments.append(
                    {
                        "start_sample": start,
                        "end_sample": end,
                        "detector_end_sample_including_padding": raw_end,
                        "sample_rate": POLICY["sample_rate"],
                        "pcm_base64": base64.b64encode(pcm).decode("ascii"),
                        "timing_scope": "Received PCM sample clock; excludes mute/disconnect wall-clock gaps. VAD boundary is model inference.",
                        "pre_roll_seconds": POLICY["pre_roll_seconds"],
                    }
                )
            self.detector.pop()
        return segments

    def feed(self, pcm: bytes, flush: bool = False) -> dict[str, Any]:
        """Process actual PCM, report transitions and clip flush padding to real source duration."""
        if len(pcm) % 2 or len(pcm) > POLICY["max_pcm_message_bytes"]:
            raise SireError(
                "invalid_voice_frame", "Use bounded PCM16 mono16kHz frames.", 422
            )
        self.received_samples += len(pcm) // 2
        self.source_pcm.extend(pcm)
        excess = (
            len(self.source_pcm)
            - int(POLICY["source_buffer_seconds"] * POLICY["sample_rate"]) * 2
        )
        if excess > 0:
            del self.source_pcm[:excess]
            self.source_base += excess // 2
        self.pending.extend(pcm)
        started = False
        while len(self.pending) >= 1024:
            block = bytes(self.pending[:1024])
            del self.pending[:1024]
            self.detector.accept_waveform(
                self.np.frombuffer(block, dtype="<i2").astype(self.np.float32) / 32768
            )
            detected = self.detector.is_speech_detected()
            started |= detected and not self.speaking
            self.speaking = detected
        if flush:
            if self.pending:
                block = bytes(self.pending) + bytes(1024 - len(self.pending))
                self.pending.clear()
                self.detector.accept_waveform(
                    self.np.frombuffer(block, dtype="<i2").astype(self.np.float32)
                    / 32768
                )
            self.detector.flush()
            self.speaking = False
        return {
            "speech_started": started,
            "speaking": self.speaking,
            "segments": self._collect(),
            "received_samples": self.received_samples,
        }

    def reset(self) -> None:
        """Discard the pending utterance on mute while retaining a monotonic received-sample clock."""
        self.detector.reset()
        self.pending.clear()
        self.base_samples = self.received_samples
        self.speaking = False
        self.source_pcm.clear()
        self.source_base = self.received_samples
        self.last_segment_end = self.received_samples
