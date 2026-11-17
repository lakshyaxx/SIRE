"""Actual bounded recording decode, explicit industrial schemas and provenance checks."""

import hashlib
import sys
from pathlib import Path
import pytest
from app.core.errors import SireError
from app.evidence.measurements import parse, profile
from app.evidence.ledger import Ledger
from app.knowledge.ingestion import ingest
from app.media import runtime
from app.media.video import validate_container


def measurements() -> bytes:
    """Return explicitly test-only input, never a production result."""
    return b"asset_id,timestamp,channel,value,unit\nTEST-PUMP,2026-01-01T00:00:00Z,vibration,1,mm/s\nTEST-PUMP,2026-01-01T01:00:00Z,vibration,3,mm/s\n"


def test_industrial_rows_actual_summary_and_domain_separation(store):
    cid = store.create_conversation()["id"]
    item = ingest(store, cid, "test-only-measurements.csv", measurements())
    assert not item["metadata"]["prediction_eligible"]
    assert item["metadata"]["measurement_schema"]["asset_ids"] == ["TEST-PUMP"]
    result = profile(store, cid, item["id"])
    assert result["groups"][0]["count"] == 2 and result["groups"][0]["recent_mean"] == 2
    source = Ledger(store).resolve(result["evidence_ids"][0])
    assert source["evidence"]["source_type"] == "real_uploaded"
    assert source["evidence"]["observation"]["rows"][1]["source_row"] == 2
    assert source["source"]["sha256"] == hashlib.sha256(measurements()).hexdigest()


@pytest.mark.parametrize(
    "content",
    [
        measurements().replace(b"2026-01-01T00:00:00Z", b"2026-01-01T00:00:00"),
        measurements().replace(b",3,mm/s", b",NaN,mm/s"),
        measurements().replace(b",3,mm/s", b",3,g"),
        measurements()
        .replace(b",1,mm/s", b",-274,degC")
        .replace(b",3,mm/s", b",3,degC"),
    ],
)
def test_invalid_declared_measurements_rejected(content):
    with pytest.raises(SireError):
        parse(content, ".csv")


def test_unknown_schema_stays_generic_and_playlists_are_not_video():
    assert parse(b"id,value\na,1\n", ".csv") is None
    with pytest.raises(SireError, match="genuine"):
        validate_container(b"#EXTM3U\nhttps://external.example/segment", ".mp4")


@pytest.mark.skipif(
    not (runtime.DEPENDENCIES / "cv2").is_dir(),
    reason="Optional local OpenCV runtime not provisioned",
)
def test_real_video_decode_timestamps_and_retained_child_frames(store, tmp_path):
    sys.path.insert(0, str(runtime.DEPENDENCIES))
    import cv2
    import numpy as np

    path = tmp_path / "test-only-encoded.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    assert writer.isOpened()
    for index in range(20):
        frame = np.zeros((48, 64, 3), np.uint8)
        frame[:, :, 2] = index * 10
        writer.write(frame)
    writer.release()
    output = runtime.run("video", {"path": str(path)})
    assert output["decoded_frames"] == 20
    assert len(output["frames"]) == min(runtime.POLICY["max_video_frames"], 20)
    assert output["frames"][0]["timestamp_seconds"] == 0
    assert output["frames"][-1]["timestamp_seconds"] == pytest.approx(1.9)
    cid = store.create_conversation()["id"]
    item = ingest(store, cid, "test-only-encoded.mp4", path.read_bytes())
    assert item["kind"] == "video" and item["metadata"]["video"]["decoded_frames"] == 20
    for frame in item["metadata"]["video"]["frames"]:
        child = store.attachment(frame["attachment_id"], cid)
        assert child["metadata"]["parent_attachment_id"] == item["id"]
        assert (
            child["metadata"]["video_timestamp_seconds"] == frame["timestamp_seconds"]
        )
        assert child["sha256"] == frame["sha256"]
        assert (
            hashlib.sha256(Path(child["path"]).read_bytes()).hexdigest()
            == frame["sha256"]
        )


@pytest.mark.parametrize(
    "suffix,format_name", [(".flac", "FLAC"), (".ogg", "OGG"), (".mp3", "MP3")]
)
@pytest.mark.skipif(
    not (runtime.DEPENDENCIES / "soundfile.py").exists()
    or not (runtime.MODELS / "whisper-tiny-en/0.wav").exists(),
    reason="Optional local audio fixtures/runtime not provisioned",
)
def test_real_compressed_audio_transcription(suffix, format_name, tmp_path):
    sys.path.insert(0, str(runtime.DEPENDENCIES))
    import soundfile as sf
    from app.voice.service import transcribe_bytes

    samples, rate = sf.read(str(runtime.MODELS / "whisper-tiny-en/0.wav"))
    path = tmp_path / ("test-only-compressed" + suffix)
    sf.write(str(path), samples, rate, format=format_name)
    result = transcribe_bytes(path.read_bytes(), suffix=suffix)
    assert "yellow lamps" in result["text"].casefold()
    assert result["format"]["decoder"] == "libsndfile"
    assert result["original_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
