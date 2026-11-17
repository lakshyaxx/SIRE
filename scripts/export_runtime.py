"""Export a private relocatable source/native-inference bundle without user state."""

import hashlib
import argparse
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.prediction.hub import manifest, verify_integrity


def bundle_files() -> list[Path]:
    """Select application sources and explicitly indexed native dependencies only."""
    paths = set()
    excluded = {
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "migration_tools",
        "history",
        "dist-v3",
        "SCENARIO_GROUND_TRUTH_INTERNAL.md",
    }
    for folder in [
        "app",
        "web",
        "config",
        "data",
        "tests",
        "scripts",
        "docs",
        "ml/registry",
    ]:
        for path in (ROOT / folder).rglob("*"):
            relative = path.relative_to(ROOT)
            if (
                path.is_file()
                and not excluded.intersection(relative.parts)
                and not relative.as_posix().startswith(
                    ("data/imports/", "data/scenarios/")
                )
                and path.suffix not in {".pyc", ".tsbuildinfo"}
            ):
                paths.add(path)
    for name in [
        "README.md",
        "AGENTS.md",
        "STATUS.md",
        ".env.example",
        ".gitignore",
        "pyproject.toml",
        "requirements-app.txt",
        "requirements-app.lock.txt",
        "requirements-runtime.lock.txt",
        "requirements-media.lock.txt",
    ]:
        paths.add(ROOT / name)
    paths.update(ROOT / record["path"] for record in manifest()["integrity_files"])
    for path in paths:
        if not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise ValueError("Export input is missing or leaves the workspace")
    return sorted(paths)


def main() -> None:
    """Write and CRC/hash-verify the ignored private ZIP and its file manifest."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["v3", "v3_2"], default="v3_2")
    args = parser.parse_args()
    verify_integrity()
    files = bundle_files()
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    destination = output / f"sire_{args.version}_local_runtime.zip"
    temporary_destination = destination.with_suffix(".zip.partial")
    records = []
    with zipfile.ZipFile(
        temporary_destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for path in files:
            content = path.read_bytes()
            name = path.relative_to(ROOT).as_posix()
            archive.writestr(name, content)
            records.append(
                {
                    "path": name,
                    "bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
    with zipfile.ZipFile(temporary_destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC verification failed")
        for record in records:
            if (
                hashlib.sha256(archive.read(record["path"])).hexdigest()
                != record["sha256"]
            ):
                raise ValueError("ZIP content hash verification failed")
    temporary_destination.replace(destination)
    result = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(files),
        "uncompressed_bytes": sum(row["bytes"] for row in records),
        "zip_bytes": destination.stat().st_size,
        "zip_sha256": hashlib.file_digest(destination.open("rb"), "sha256").hexdigest(),
        "private_distribution_only": True,
        "excluded": [
            "user conversations/uploads",
            "Python environments",
            "Node modules",
            "Ollama runtime/weights",
            "research archive",
            "Git history",
        ],
        "files": records,
    }
    (output / f"sire_{args.version}_local_runtime.manifest.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "files"}, indent=2
        )
    )


if __name__ == "__main__":
    main()
