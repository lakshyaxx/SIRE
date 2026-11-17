"""Optional artifact integrity safeguards without network access or native model loading."""

import hashlib
import pytest
from scripts.setup_media import download


def test_cached_artifact_mismatch_is_preserved_and_refused(tmp_path):
    path = tmp_path / "test-only-cache.bin"
    path.write_bytes(b"test-only-tampered-content")
    expected = hashlib.sha256(b"test-only-expected-content").hexdigest()
    with pytest.raises(ValueError, match="differs"):
        download("https://example.invalid/never-contacted", path, expected)
    assert path.read_bytes() == b"test-only-tampered-content"


def test_verified_cached_artifact_requires_no_download(tmp_path, monkeypatch):
    from scripts import setup_media

    path = tmp_path / "test-only-cache.bin"
    content = b"test-only-verified-source"
    path.write_bytes(content)

    def refuse_network(*args, **kwargs):
        raise AssertionError("Unnecessary network call for verified cached bytes")

    monkeypatch.setattr(setup_media.urllib.request, "build_opener", refuse_network)
    download(
        "https://example.invalid/never-contacted",
        path,
        hashlib.sha256(content).hexdigest(),
    )
    assert path.read_bytes() == content
