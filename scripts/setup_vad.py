"""Provision only the pinned small MIT Silero model into the existing isolated local media runtime."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.media.runtime import MODELS, POLICY
from scripts.setup_media import download


def main() -> None:
    """Verify cached files or fetch bounded official artifacts; never modify the research environment."""
    spec = POLICY["models"]["vad"]
    directory = MODELS / spec["directory"]
    directory.mkdir(parents=True, exist_ok=True)
    download(
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx",
        directory / "silero_vad.onnx",
        spec["files"]["silero_vad.onnx"],
        maximum=5000000,
    )
    download(
        "https://raw.githubusercontent.com/snakers4/silero-vad/master/LICENSE",
        directory / "LICENSE",
        "2e63e9a38b6e8fc0c7bc37ce174caca1862870856c6daf5697cfb785e925520b",
        maximum=20000,
    )


if __name__ == "__main__":
    main()
