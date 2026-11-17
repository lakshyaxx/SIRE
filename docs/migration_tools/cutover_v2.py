"""One-time reversible active-tree retirement, guarded by inference and backup evidence."""

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = Path.home() / "SIRE_SAFETY_BACKUPS/v2_retired_20261117"


def cutover() -> None:
    """Move exact named old roots into quarantine; never delete, overwrite or touch Git."""
    if ARCHIVE.exists():
        raise RuntimeError(
            "Retirement destination already exists; inspect its manifest before resuming"
        )
    checks = json.loads((ROOT / "ml/registry/verification.json").read_text())
    catalog = json.loads((ROOT / "ml/registry/catalog.json").read_text())
    if len(checks) != len(catalog["models"]) or any(
        row["status"] != "ready" for row in checks.values()
    ):
        raise RuntimeError("Every consolidated route must have passed real inference")
    snapshot = Path.home() / "SIRE_SAFETY_BACKUPS/v2_20261117_000722/manifest.json"
    if not snapshot.is_file():
        raise RuntimeError("Verified pre-build snapshot is missing")
    for record in catalog["integrity_files"]:
        path = ROOT / record["path"]
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != record["sha256"]:
                raise RuntimeError("Native dependency changed before cutover")
    moves = [(ROOT / "Phase_A_RUL_Training/.venv", ARCHIVE / "environment")]
    folders = [
        "Phase_A_RUL_Training",
        "Phase_B_LLM_Integration",
        "Phase_C_Knowledge_RAG",
        "Phase_D_Hypothesis_Engine",
        "Phase_E_Vision",
        "Phase_F_Frontend_Voice",
        "Phase_G_Final_Integration",
        "engine",
        "backend",
        "frontend",
        "model_store",
        "samples",
        "_archive",
        "output",
        "migration_staging",
    ]
    moves += [(ROOT / name, ARCHIVE / "research_and_v1" / name) for name in folders]
    moves += [
        (path, ARCHIVE / "v1_tests" / path.name)
        for path in (ROOT / "tests").glob("*.py")
    ]
    obsolete = ["inventory.py", "verify_models.py", "package_demo.py", "smoke_test.py"]
    moves += [
        (ROOT / "scripts" / name, ARCHIVE / "v1_scripts" / name) for name in obsolete
    ]
    for source, target in moves:
        resolved_source, resolved_target = source.resolve(), target.resolve()
        if not resolved_source.is_relative_to(
            ROOT.resolve()
        ) or not resolved_target.is_relative_to(ARCHIVE.resolve()):
            raise RuntimeError("Move escaped the exact workspace/archive scope")
        if source.is_symlink() or target.exists() or not source.exists():
            raise RuntimeError(f"Unexpected move state: {source.name}")
    ARCHIVE.mkdir(parents=True)
    ledger = {
        "snapshot": str(snapshot),
        "mode": "reversible relocation; no permanent deletion",
        "moves": [],
    }
    manifest = ARCHIVE / "retirement_manifest.json"
    for source, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True)
        os.rename(source, target)
        ledger["moves"].append({"old_path": str(source), "archive_path": str(target)})
        manifest.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        print("RETIRED", source.relative_to(ROOT), flush=True)
        if target == ARCHIVE / "environment":
            pth = ROOT / ".venv/Lib/site-packages/sire-preserved-runtime.pth"
            pth.write_text(str(target / "Lib/site-packages") + "\n", encoding="utf-8")
    (ROOT / "docs/RETIREMENT_MANIFEST.json").write_text(
        json.dumps(ledger, indent=2), encoding="utf-8"
    )
    print("ARCHIVE", ARCHIVE, flush=True)


if __name__ == "__main__":
    if sys.argv[1:] != ["--execute"]:
        raise SystemExit(
            "Read the exact move set and verified backup before using --execute"
        )
    cutover()
