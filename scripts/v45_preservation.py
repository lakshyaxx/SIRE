"""Read-only verification of V45 protected native files, old table rows and frozen test artifacts."""

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.prediction.hub import manifest, verify_integrity


def main() -> None:
    """Save exact comparisons without modifying a protected database, model or stress result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / ".runtime/v45").resolve()) or output.exists():
        raise SystemExit("Use a new result file within the V45 namespace")
    began = time.monotonic()
    result = {
        "native_integrity_files": verify_integrity(),
        "tables": [],
        "stress_mismatches": [],
        "bundles": [],
    }
    baseline = ROOT / ".runtime/v45/backups/pre_edit_production.sqlite3"
    production = ROOT / ".runtime/v2/sire.sqlite3"
    with (
        sqlite3.connect(baseline.as_uri() + "?mode=ro", uri=True) as old,
        sqlite3.connect(production.as_uri() + "?mode=ro", uri=True) as current,
    ):
        tables = [
            row[0]
            for row in old.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            previous = old.execute(f"SELECT * FROM {quoted} ORDER BY rowid").fetchall()
            present = current.execute(
                f"SELECT * FROM {quoted} ORDER BY rowid"
            ).fetchall()
            result["tables"].append(
                {
                    "table": table,
                    "rows_before": len(previous),
                    "rows_after": len(present),
                    "equal": previous == present,
                }
            )
        result["additive_tables"] = sorted(
            {
                row[0]
                for row in current.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            - set(tables)
        )
    frozen = json.loads(
        (ROOT / ".runtime/v4/preflight.json").read_text(encoding="utf-8")
    )["stress_files"]
    result["stress_files_checked"] = len(frozen)
    for relative, expected in frozen.items():
        path = ROOT / relative
        if not path.is_file():
            result["stress_mismatches"].append({"path": relative, "reason": "missing"})
            continue
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != expected["sha256"] or path.stat().st_size != expected["bytes"]:
            result["stress_mismatches"].append({"path": relative, "reason": "changed"})
    expected_bundles = {
        "sire_v2_local_runtime.zip": "18c9bb7c20af2ca43cf470d9594c72313a129011304521c07ca90bd50b5f3f24",
        "sire_v3_local_runtime.zip": "e7ea3c9f7e287a88118ddfe3c77697a530287c7ec6b13e09edda4719d5505ac8",
        "sire_v3_2_local_runtime.zip": "7137fd98e6ee6fd38a8d7adebc513cdca0d3a2b2e16ede147d6a0a479017093a",
    }
    for name, expected in expected_bundles.items():
        path = ROOT / "output" / name
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        result["bundles"].append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": digest,
                "equal": digest == expected,
            }
        )
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=no"], cwd=ROOT, text=True
    )
    result["inherited_deleted_path_count"] = sum(
        "D" in row[:2] for row in status.splitlines()
    )
    result["native_routes_retained"] = len(manifest()["models"])
    result["elapsed_seconds"] = time.monotonic() - began
    result["status"] = (
        "pass"
        if all(row["equal"] for row in result["tables"] + result["bundles"])
        and not result["stress_mismatches"]
        and result["inherited_deleted_path_count"] == 2792
        else "fail"
    )
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
