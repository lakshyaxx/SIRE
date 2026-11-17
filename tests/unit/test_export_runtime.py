"""Ensure the private export includes indexed dependencies and excludes user/environment state."""

from scripts.export_runtime import ROOT, bundle_files
from app.prediction.hub import manifest


def test_export_has_all_native_inputs_and_no_private_state():
    names = {p.relative_to(ROOT).as_posix() for p in bundle_files()}
    assert {r["path"] for r in manifest()["integrity_files"]}.issubset(names)
    assert "web/dist/index.html" in names
    assert not any(
        name.startswith(
            (
                ".runtime/",
                ".venv/",
                "web/node_modules/",
                ".git/",
                "data/imports/",
                "data/scenarios/",
            )
        )
        for name in names
    )
    assert not any(name.endswith((".sqlite3", ".pyc")) for name in names)
