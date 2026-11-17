"""Loaded-source identity changes with shipped code, excluding protected research."""

from app.core.runtime_identity import source_identity
from app.voice.text import display_safe_text


def test_identity_tracks_code_and_frontend_but_not_research(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "config").mkdir()
    frontend = tmp_path / "web"
    frontend.mkdir()
    source = tmp_path / "app/test_only.py"
    source.write_text("value = 1", encoding="utf-8")
    initial = source_identity(tmp_path, frontend)
    (tmp_path / "research.txt").write_text("test fixture", encoding="utf-8")
    assert source_identity(tmp_path, frontend) == initial
    source.write_text("value = 2", encoding="utf-8")
    changed = source_identity(tmp_path, frontend)
    assert changed != initial
    (frontend / "index.html").write_text("test index", encoding="utf-8")
    assert source_identity(tmp_path, frontend) != changed


def test_spoken_display_omits_markup_identifiers_urls_and_code():
    result = display_safe_text(
        "## Reading 2.685 mm/s [EV:" + "a" * 64 + "]\n"
        "[Manual](https://example.invalid/manual) ```ignore this code``` <b>Review</b>"
    )
    assert result == "Reading 2.685 mm/s Manual Review"
