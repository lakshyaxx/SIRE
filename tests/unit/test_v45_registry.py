"""Real provider inventory does not load optional weights or invent availability on an outage."""

from app.core.errors import SireError
from app.providers import registry


def test_registry_marks_missing_provider_and_optional_adapters_honestly(monkeypatch):
    def unavailable(*args):
        raise SireError(
            "test_only_unavailable", "Explicit test-only provider outage", 503
        )

    monkeypatch.setattr(registry.OllamaAdapter, "list_models", unavailable)
    rows = registry.providers()
    assert rows and all(
        row.availability == "unavailable" for row in rows if row.provider == "ollama"
    )
    optional = [row for row in rows if row.provider == "optional"]
    assert len(optional) == (
        2 if registry.runtime.readiness().get("vad_configured") else 3
    ) and all(
        row.adapter is None and row.availability == "optional_not_installed"
        for row in optional
    )
    assert all(row.input_schema and row.output_schema and row.license for row in rows)
    assert any(row.provider == "preserved_native" for row in rows)
    assert any(
        row.id == "local:retrieval" and row.adapter == "app.knowledge.search.search"
        for row in rows
    )


def test_resource_status_does_not_turn_unreachable_residency_into_empty_models(
    monkeypatch,
):
    import httpx

    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("Explicit test-only isolated failure")

    monkeypatch.setattr(registry.httpx, "get", unavailable)
    result = registry.resources()
    assert result["ollama_residency"]["models"] is None
    assert result["ollama_residency"]["status"] == "unavailable"
    assert result["scheduler"]["heavy_slots"] == 1
