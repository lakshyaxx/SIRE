"""Explicit bounded optional specialist installation; never called during user inference."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Review or install only the pinned approved local model/runtime assets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    parser.add_argument(
        "--group", choices=["semantic", "asr_base", "all"], default="all"
    )
    args = parser.parse_args()
    spec = json.loads(
        (ROOT / "config/specialists.lock.json").read_text(encoding="utf-8")
    )
    files = [
        f
        for f in spec["files"]
        if args.group == "all"
        or f["group"]
        in {args.group, "semantic_runtime" if args.group == "semantic" else args.group}
    ]
    total = sum(f["bytes"] for f in files)
    if total > spec["max_download_bytes"]:
        raise SystemExit("Manifest exceeds download budget")
    print(
        json.dumps(
            {
                "group": args.group,
                "files": len(files),
                "bytes_if_all_absent": total,
                "licenses": spec["licenses"],
                "action": "install" if args.install else "review only",
            },
            indent=2,
        )
    )
    if not args.install:
        return
    if any(f["group"] == "semantic_runtime" for f in files) and (
        os.name != "nt" or sys.maxsize < 2**32
    ):
        raise SystemExit(
            "The reviewed runtime wheels target Windows x64; other platforms require a separately reviewed wheel manifest."
        )
    receipt = []
    with httpx.Client(timeout=120, follow_redirects=True, trust_env=False) as client:
        for row in files:
            path = (ROOT / row["path"]).resolve()
            if not any(
                path.is_relative_to(ROOT / base)
                for base in [
                    ".runtime/semantic_models",
                    ".runtime/media_models/whisper-base.en",
                    ".runtime/phase2_setup/wheels",
                ]
            ):
                raise SystemExit("Unsafe installation target")
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                with path.open("rb") as stream:
                    actual = hashlib.file_digest(stream, "sha256").hexdigest()
                if actual != row["sha256"]:
                    raise SystemExit(
                        "Existing candidate hash differs; preserved without replacement: "
                        + row["path"]
                    )
                receipt.append({"path": row["path"], "status": "verified existing"})
                continue
            with tempfile.NamedTemporaryFile(
                dir=path.parent, prefix="download-", suffix=".part", delete=False
            ) as stream:
                temporary = Path(stream.name)
                digest = hashlib.sha256()
                size = 0
                with client.stream("GET", row["url"]) as response:
                    response.raise_for_status()
                    for part in response.iter_bytes(1024 * 1024):
                        size += len(part)
                        if size > row["bytes"]:
                            raise SystemExit("Download exceeded pinned size")
                        stream.write(part)
                        digest.update(part)
            if size != row["bytes"] or digest.hexdigest() != row["sha256"]:
                raise SystemExit(
                    "Downloaded candidate failed integrity; partial file retained for inspection"
                )
            if path.exists():
                raise SystemExit(
                    "Candidate appeared during download; refusing replacement"
                )
            temporary.replace(path)
            receipt.append(
                {"path": row["path"], "status": "downloaded and SHA256 verified"}
            )
    wheels = [str(ROOT / f["path"]) for f in files if f["group"] == "semantic_runtime"]
    if wheels:
        destination = ROOT / ".runtime/semantic_deps"
        if not destination.exists():
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--no-deps",
                    "--target",
                    str(destination),
                    *wheels,
                ],
                check=True,
            )
        else:
            print(
                "Existing isolated runtime retained; run the documented local inference check."
            )
    directory = ROOT / ".runtime/phase2_setup"
    directory.mkdir(exist_ok=True)
    (directory / "installation.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
