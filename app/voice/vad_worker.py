"""Private line-delimited VAD protocol; optional neural modules never enter the API process."""

import base64
import json
import sys
from app.media.runtime import DEPENDENCIES, model_files
from app.core.errors import SireError


def main() -> None:
    """Accept only bounded feed/reset/flush operations; no client paths or executable commands."""
    sys.path.insert(0, str(DEPENDENCIES))
    from app.voice.vad import VadStream

    detector = VadStream(model_files("vad")["silero_vad.onnx"])
    from app.media.runtime import MODELS, POLICY
    from app.evidence.ledger import digest
    from app.storage.database import now

    (MODELS / "silero-vad/verified.json").write_text(
        json.dumps(
            {
                "model_fingerprint": digest(POLICY["models"]["vad"]["files"]),
                "probe": "Actual Silero VAD initialized in isolated worker",
                "timestamp": now(),
            }
        ),
        encoding="utf-8",
    )
    sys.stdout.write(
        json.dumps({"type": "ready", "model": "silero_vad.onnx", "sample_rate": 16000})
        + "\n"
    )
    sys.stdout.flush()
    for line in sys.stdin:
        try:
            if len(line) > 50000:
                raise SireError(
                    "invalid_voice_frame", "Voice frame exceeds the worker budget.", 413
                )
            request = json.loads(line)
            if request["op"] == "reset":
                detector.reset()
                result = {"reset": True}
            elif request["op"] in {"feed", "flush"}:
                pcm = base64.b64decode(request.get("pcm_base64", ""), validate=True)
                result = detector.feed(pcm, flush=request["op"] == "flush")
            else:
                raise SireError(
                    "invalid_voice_control", "Unsupported voice control.", 422
                )
            sys.stdout.write(json.dumps(result) + "\n")
            sys.stdout.flush()
        except (SireError, ValueError, KeyError) as exc:
            sys.stdout.write(
                json.dumps(
                    {
                        "error": {
                            "code": getattr(exc, "code", "invalid_voice_frame"),
                            "message": "Voice worker rejected this frame/control.",
                        }
                    }
                )
                + "\n"
            )
            sys.stdout.flush()


if __name__ == "__main__":
    main()
