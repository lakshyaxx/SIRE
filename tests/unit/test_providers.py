"""Provider failure and injection checks using explicitly test-only responses."""

import io

import pytest
from PIL import Image

from app.providers import ollama as providers
from app.core.config import SETTINGS
from app.core.errors import SireError


def test_no_hosted_transmission(monkeypatch):
    monkeypatch.setitem(SETTINGS, "ollama_base_url", "https://example.com")
    with pytest.raises(SireError):
        providers._base()


def test_invalid_photo():
    with pytest.raises(SireError, match="valid JPEG"):
        providers.analyze_image(b"not an image", "question", "")


def test_no_vision(monkeypatch):
    image = Image.new(
        "RGB", (2, 2)
    )  # Explicit test-only image, no production observations.
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    monkeypatch.setattr(providers, "readiness", lambda: {"vision_ready": False})
    with pytest.raises(SireError, match="vision model is unavailable"):
        providers.analyze_image(buffer.getvalue(), "question", "")
