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


def test_primary_native_models_resolve_under_preserved_cmapss_root(monkeypatch):
    """Discovery must describe the same relocated artifacts that actual inference uses."""
    from app.prediction.policy import selections
    from app.core.config import ROOT, TRACK

    monkeypatch.setattr(registry.OllamaAdapter, "list_models", lambda self: [])
    selected = {
        "native:" + model for roles in selections().values() for model in roles.values()
    }
    rows = [row for row in registry.providers() if row.id in selected]
    assert {row.id for row in rows} == selected
    assert all(row.availability == "configured" for row in rows)
    assert all(
        (ROOT / row.location).resolve().is_relative_to(TRACK.resolve()) for row in rows
    )
