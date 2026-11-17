"""Bounded local video frame decoding with actual decoder timestamps and source pointers."""

import hashlib
import math
from pathlib import Path
from app.core.errors import SireError
from app.media.runtime import POLICY


def validate_container(content: bytes, suffix: str) -> None:
    """Reject playlists, URLs and disguised unsupported containers before native decoding."""
    valid = (
        (suffix in {".mp4", ".mov"} and len(content) >= 12 and content[4:8] == b"ftyp")
        or (
            suffix == ".avi"
            and content.startswith(b"RIFF")
            and content[8:12] == b"AVI "
        )
        or (suffix in {".webm", ".mkv"} and content.startswith(b"\x1a\x45\xdf\xa3"))
    )
    if not valid:
        raise SireError(
            "invalid_video_container",
            "Use a genuine bounded MP4/MOV (ftyp), AVI, WebM or MKV clip.",
            422,
        )


def sample_frames(path: Path, workspace: Path) -> dict:
    """Decode at most the configured duration/count and preserve actual frame positions."""
    import cv2

    with path.open("rb") as source:
        validate_container(source.read(64), path.suffix.lower())
    cv2.setNumThreads(POLICY["threads"])
    capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    try:
        if not capture.isOpened():
            raise SireError(
                "video_decode_failed",
                "The local decoder could not open this clip.",
                422,
            )
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(
            capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        )
        if not math.isfinite(fps) or not 0 < fps <= 120 or count <= 0:
            raise SireError(
                "video_timing_unavailable",
                "Clip lacks usable bounded frame-rate/count metadata; no timestamps were guessed.",
                422,
            )
        if (
            width * height > POLICY["max_frame_pixels"]
            or width <= 0
            or height <= 0
            or count > POLICY["max_decoded_frames"]
            or count / fps > POLICY["max_video_seconds"]
        ):
            raise SireError(
                "video_limits",
                "Clip exceeds the configured 60-second, frame-count or resolution budget.",
                413,
            )
        samples = min(POLICY["max_video_frames"], count)
        targets = {round(i * (count - 1) / max(1, samples - 1)) for i in range(samples)}
        frames = []
        decoded = 0
        last_time = None
        missing_times = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if (
                decoded >= POLICY["max_decoded_frames"]
                or frame.shape[0] * frame.shape[1] > POLICY["max_frame_pixels"]
            ):
                raise SireError(
                    "video_limits", "Decoded frames exceed resource limits.", 413
                )
            timestamp = float(capture.get(cv2.CAP_PROP_POS_MSEC)) / 1000
            if (
                not math.isfinite(timestamp)
                or timestamp < 0
                or (
                    decoded > 0
                    and (
                        timestamp == 0
                        or (last_time is not None and timestamp <= last_time)
                    )
                )
            ):
                timestamp = None
                missing_times += 1
            if timestamp is not None:
                if timestamp > POLICY["max_video_seconds"]:
                    raise SireError(
                        "video_limits",
                        "Actual decoder timestamp exceeds the duration limit.",
                        413,
                    )
                last_time = timestamp
            if decoded in targets:
                ratio = min(1, 1280 / max(frame.shape[:2]))
                if ratio < 1:
                    frame = cv2.resize(
                        frame,
                        (round(frame.shape[1] * ratio), round(frame.shape[0] * ratio)),
                    )
                filename = f"frame-{decoded:06d}.jpg"
                success, encoded = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85]
                )
                if not success:
                    raise SireError(
                        "video_frame_encode",
                        "A real decoded frame could not be preserved.",
                        422,
                    )
                content = encoded.tobytes()
                (workspace / filename).write_bytes(content)
                frames.append(
                    {
                        "frame_number": decoded,
                        "timestamp_seconds": timestamp,
                        "timestamp_method": (
                            "decoder_CAP_PROP_POS_MSEC"
                            if timestamp is not None
                            else "unavailable; frame index only"
                        ),
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "file": filename,
                        "width": frame.shape[1],
                        "height": frame.shape[0],
                    }
                )
            decoded += 1
        if not frames:
            raise SireError("video_empty", "No real video frame was decoded.", 422)
        return {
            "frames": frames,
            "decoded_frames": decoded,
            "reported_frame_count": count,
            "reported_fps": fps,
            "last_observed_decoder_timestamp_seconds": last_time,
            "missing_timestamp_count": missing_times,
            "sampling_policy": "Uniform target frame indices from reported count; returned timestamps are actual decoder positions, never inferred wall-clock time.",
            "codec": "OpenCV 4.12.0 / LGPL FFmpeg",
            "limitations": [
                "Sampled still frames do not establish behavior between frames or a mechanical cause.",
                "Video audio track is not transcribed; upload an audio recording separately.",
                "Container and decoder timing metadata are unverified source metadata.",
            ],
        }
    finally:
        capture.release()
