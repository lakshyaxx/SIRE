"""V2 fixtures: temporary stores and explicitly test-only provider responses."""

import pytest
import asyncio
from app.storage.database import Store


@pytest.fixture
def sync_proposal_transport(monkeypatch):
    """Adapt explicit legacy synchronous proposal fixtures to the new asynchronous transport.

    Only marked unit modules use this bridge. Production and real inference tests call
    generate_async directly; no runtime fixture detection or substitute is installed.
    """
    from app.providers import ollama

    async def call(messages, schema, model, cancelled):
        return await asyncio.to_thread(ollama.generate, messages, schema, model)

    monkeypatch.setattr(ollama, "generate_async", call)


class TestOnlyProvider:
    """Deterministic transport fixture; never selected by production configuration."""

    __test__ = False

    def __init__(self):
        self.requests = []

    def health(self):
        return {
            "ollama_ready": False,
            "text_ready": False,
            "vision_ready": False,
            "models": [],
        }

    def list_models(self):
        return []

    async def stream(self, messages, model, cancelled):
        self.requests.append(messages)
        for token in ["Test-only ", "transport reply."]:
            if cancelled.is_set():
                return
            yield token

    async def vision(self, content, question):
        return {
            "provider": "test-only",
            "model": "fixture",
            "visible_observations": ["Test fixture pixel field"],
            "limitations": ["Test-only, not an actual component observation"],
        }


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "state/sire.sqlite3")


@pytest.fixture
def provider():
    return TestOnlyProvider()


@pytest.fixture
def v2client(tmp_path, provider):
    from fastapi.testclient import TestClient
    from app.api.main import create_app

    with TestClient(
        create_app(tmp_path / "state", provider, probe_model=False),
        raise_server_exceptions=False,
    ) as client:
        yield client
