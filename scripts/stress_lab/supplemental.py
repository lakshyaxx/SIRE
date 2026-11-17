"""Fresh real-domain rejection and reply-speech checks after serial corpus phases finish."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import time
import wave
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.core.config import ROOT
from app.media.runtime import model_files
from app.voice.text import spoken_text
from scripts.stress_lab.corpus import safe_fixture


def domain_boundary(client: TestClient, content: bytes, filename: str) -> dict:
    """Attempt real synthetic CSV prediction and prove rejection without a saved native output."""
    before = client.app.state.store.rows("SELECT COUNT(*) n FROM predictions")[0]["n"]
    began = time.monotonic()
    cid = (
        client.post(
            "/api/v1/conversations", json={"title": "Stress synthetic/NASA boundary"}
        )
        .raise_for_status()
        .json()["id"]
    )
    uploaded = client.post(
        "/api/v1/attachments",
        data={"conversation_id": cid},
        files={"file": (filename, content)},
    )
    uploaded.raise_for_status()
    attachment = uploaded.json()
    result = client.post(
        "/api/v1/predictions/run",
        json={
            "dataset": "FD001",
            "model_id": "fd001-01_lightgbm-s42",
            "attachment_id": attachment["id"],
        },
    )
    forced = client.post(
        "/api/v1/predictions/upload",
        data={"dataset": "FD001", "compatible_cmapss": "true"},
        files={"file": (filename, content)},
    )
    forced_body = forced.json()
    forced_prediction = None
    if forced.status_code == 200:
        forced_prediction = client.post(
            "/api/v1/predictions/run",
            json={
                "dataset": "FD001",
                "model_id": "fd001-01_lightgbm-s42",
                "attachment_id": forced_body["id"],
            },
        )
    forced_safe = forced.status_code in {400, 422} or (
        forced.status_code == 200
        and forced_body.get("metadata", {}).get("prediction_eligible") is False
        and forced_prediction is not None
        and forced_prediction.status_code in {400, 422}
    )
    after = client.app.state.store.rows("SELECT COUNT(*) n FROM predictions")[0]["n"]
    return {
        "elapsed_seconds": time.monotonic() - began,
        "fixture_sha256": hashlib.sha256(content).hexdigest(),
        "attachment_id": attachment["id"],
        "prediction_eligible": attachment["metadata"].get("prediction_eligible"),
        "prediction_status": result.status_code,
        "prediction_response": result.json(),
        "forced_declaration_upload_status": forced.status_code,
        "forced_declaration_response": forced_body,
        "forced_prediction_status": (
            forced_prediction.status_code if forced_prediction is not None else None
        ),
        "forced_prediction_response": (
            forced_prediction.json() if forced_prediction is not None else None
        ),
        "prediction_rows_before": before,
        "prediction_rows_after": after,
        "passed": result.status_code in {400, 422} and forced_safe and before == after,
    }


def main() -> None:
    """Generate actual local WAV from a saved corpus reply; do not claim physical playback."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output-name", default="supplemental")
    parser.add_argument("--speech-only", action="store_true")
    args = parser.parse_args()
    if Path(args.output_name).name != args.output_name:
        raise SystemExit("Output name must be a single namespace component")
    directory = args.state.resolve() / args.output_name
    if not directory.is_relative_to((ROOT / ".runtime/stress_lab").resolve()):
        raise SystemExit("Use the disposable stress namespace")
    directory.mkdir(exist_ok=False)
    proof = {
        "scope": "Additional actual API probes; not substituted for original corpus cases. Physical microphone/speaker playback unverified."
    }
    try:
        with TestClient(
            create_app(state_dir=directory, probe_model=False),
            raise_server_exceptions=False,
        ) as client:
            if not args.speech_only:
                fixture = safe_fixture(
                    args.corpus, "test_inputs/valid/telemetry_small.csv"
                )
                proof["synthetic_nasa_boundary"] = domain_boundary(
                    client, fixture.read_bytes(), fixture.name
                )
                assert proof["synthetic_nasa_boundary"]["passed"]
            saved = json.loads(
                (args.state / "traces/P1/TST-00421.json").read_text(encoding="utf-8")
            )
            text = saved["answer"][:160]
            assert text
            normalized, normalization_warnings = spoken_text(
                text, model_files("tts")["lexicon-en-us.txt"]
            )
            began = time.monotonic()
            response = client.post("/api/v1/voice/speak", json={"text": text})
            proof["tts_status"] = response.status_code
            if response.status_code != 200:
                proof["tts_error"] = response.json()
                raise RuntimeError("Actual reply synthesis failed")
            with wave.open(io.BytesIO(response.content), "rb") as recording:
                frames, rate = recording.getnframes(), recording.getframerate()
                assert frames > 0 and rate > 0
                proof["actual_reply_speech"] = {
                    "input_case": "TST-00421",
                    "input_text": text,
                    "input_characters": len(text),
                    "independently_normalized_text": normalized,
                    "normalization_warnings": normalization_warnings,
                    "frames": frames,
                    "sample_rate_hz": rate,
                    "duration_seconds": frames / rate,
                    "elapsed_seconds": time.monotonic() - began,
                    "wav_bytes": len(response.content),
                    "wav_sha256": hashlib.sha256(response.content).hexdigest(),
                    "speech_warning_count": response.headers.get("X-Speech-Warnings"),
                    "model": response.headers.get("X-Speech-Model"),
                    "hardware_playback": "Not exercised",
                }
            (directory / "actual_corpus_reply.wav").write_bytes(response.content)
            proof["status"] = "PASS for executed supplemental checks"
    except Exception as exc:
        proof.update(
            status="INCOMPLETE",
            error_type=type(exc).__name__,
            error_detail=str(exc)[:200],
        )
    (directory / "verification.json").write_text(
        json.dumps(proof, indent=2), encoding="utf-8"
    )
    print(json.dumps(proof, indent=2))
    if proof["status"] == "INCOMPLETE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
