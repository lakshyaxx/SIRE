"""Provision optional local CPU media dependencies/models without changing the preserved environment."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def download(
    url: str, destination: Path, expected: str, maximum: int = 180000000
) -> None:
    """Download a bounded HTTPS artifact atomically and verify its pinned SHA-256."""
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS sources allowed")
    if destination.is_file():
        with destination.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() == expected:
                return
        raise ValueError("Existing cached artifact differs; preserved for review")
    temporary = destination.with_suffix(destination.suffix + ".partial")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=30) as source, temporary.open("wb") as output:
        count = 0
        while block := source.read(1048576):
            count += len(block)
            if count > maximum:
                raise ValueError("Download exceeds declared resource budget")
            output.write(block)
    with temporary.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != expected:
            raise ValueError("Downloaded artifact hash mismatch")
    temporary.replace(destination)


def install_dependencies() -> None:
    """Select pinned compatible official wheels and install only into ignored optional_deps."""
    from packaging.tags import sys_tags
    from packaging.utils import parse_wheel_filename, canonicalize_name
    from app.media.runtime import DEPENDENCIES

    tags = {tag: index for index, tag in enumerate(sys_tags())}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    cache = ROOT / ".runtime/media_downloads"
    cache.mkdir(parents=True, exist_ok=True)
    records = []
    for line in (
        (ROOT / "requirements-media.lock.txt").read_text(encoding="utf-8").splitlines()
    ):
        if not line.strip() or line.startswith("#"):
            continue
        package, version = line.strip().split("==")
        existing = []
        for path in DEPENDENCIES.glob("*.dist-info/METADATA"):
            text = path.read_text(encoding="utf-8")
            if f"Version: {version}\n" in text and any(
                canonicalize_name(row.removeprefix("Name: "))
                == canonicalize_name(package)
                for row in text.splitlines()
                if row.startswith("Name: ")
            ):
                existing.append(path)
        if existing:
            continue
        with opener.open(
            f"https://pypi.org/pypi/{package}/{version}/json", timeout=20
        ) as response:
            metadata = json.load(response)
        wheels = []
        for item in metadata["urls"]:
            if item["filename"].endswith(".whl"):
                matching = parse_wheel_filename(item["filename"])[3] & tags.keys()
                if matching:
                    wheels.append((min(tags[tag] for tag in matching), item))
        if not wheels:
            raise RuntimeError("No compatible pinned wheel: " + package)
        wheel = min(wheels, key=lambda item: item[0])[1]
        destination = cache / wheel["filename"]
        download(wheel["url"], destination, wheel["digests"]["sha256"], 80000000)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--target",
                str(DEPENDENCIES),
                str(destination),
            ],
            check=True,
        )
        records.append(
            {
                "package": package,
                "version": version,
                "filename": destination.name,
                "sha256": wheel["digests"]["sha256"],
            }
        )
    if records:
        (cache / "setup_installed_wheels.json").write_text(
            json.dumps(records, indent=2), encoding="utf-8"
        )


def provision_models() -> None:
    """Extract only configured regular filenames, never arbitrary tar paths or links."""
    from app.media.runtime import MODELS, model_files

    assets = yaml.safe_load(
        (ROOT / "config/media_assets.yaml").read_text(encoding="utf-8")
    )["artifacts"]
    cache = ROOT / ".runtime/media_downloads"
    cache.mkdir(parents=True, exist_ok=True)
    for artifact in assets:
        path = cache / artifact["name"]
        download(artifact["url"], path, artifact["sha256"])
        destination = (MODELS / artifact["directory"]).resolve()
        if not destination.is_relative_to(MODELS.resolve()):
            raise ValueError("Configured model directory leaves model root")
        destination.mkdir(parents=True, exist_ok=True)
        if artifact["kind"] == "file":
            target = destination / artifact["name"]
            if not target.exists():
                target.write_bytes(path.read_bytes())
        else:
            with tarfile.open(path, "r:bz2") as archive:
                for member in archive:
                    name = Path(member.name).name
                    if (
                        member.isfile()
                        and name in artifact["allowed_files"]
                        and not (destination / name).exists()
                    ):
                        if member.size > 160000000:
                            raise ValueError("Model extraction exceeds budget")
                        with (
                            archive.extractfile(member) as source,
                            (destination / name).open("wb") as output,
                        ):
                            output.write(source.read())
    model_files("asr")
    model_files("tts")


def probe() -> dict:
    """Genuinely synthesize/transcribe audio and decode a labeled codec self-test clip."""
    from app.media.runtime import run, MODELS, DEPENDENCIES, readiness
    from app.voice.service import transcribe_bytes

    generated = run(
        "tts",
        {
            "text": "This is a simulated investigation. Independent inspection is required."
        },
    )
    recognized = transcribe_bytes(generated.pop("audio_bytes"))
    if (
        "simulated" not in recognized["text"].casefold()
        or "inspection" not in recognized["text"].casefold()
    ):
        raise RuntimeError(
            "Speech round trip did not recognize the test phrase; readiness not accepted"
        )
    sys.path.insert(0, str(DEPENDENCIES))
    import cv2
    import numpy as np

    clip = MODELS / "setup-codec-self-test.mp4"
    writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    if not writer.isOpened():
        raise RuntimeError("Codec self-test encoding unavailable")
    for index in range(10):
        frame = np.zeros((48, 64, 3), np.uint8)
        frame[:, :, 2] = index * 20
        writer.write(frame)
    writer.release()
    video = run("video", {"path": str(clip)})
    if video["decoded_frames"] != 10:
        raise RuntimeError("Codec self-test did not decode actual expected frames")
    result = {
        "tts": generated,
        "asr": recognized,
        "video": {key: value for key, value in video.items() if key != "frames"},
        "readiness": readiness(),
        "note": "Generated audio/video are explicitly labeled setup tests, never plant observations.",
    }
    (MODELS / "setup_verification.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    """Run explicit provisioning/probes; application startup never calls this installer."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Run actual bounded media models even with --verify-only",
    )
    args = parser.parse_args()
    from app.media.runtime import model_files, readiness

    if not args.verify_only:
        install_dependencies()
        provision_models()
    model_files("asr")
    model_files("tts")
    result = probe() if args.probe or not args.verify_only else readiness()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
