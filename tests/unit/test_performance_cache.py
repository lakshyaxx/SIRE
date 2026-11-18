"""Bounded reuse and integrity controls; byte payloads here are explicitly test-only cache fixtures."""

import threading
import asyncio
import ssl
import pytest
from app.media.cache import SpeechCache
from app.media import cache, runtime
from app.core.errors import SireError
from app.providers.adapter import OllamaAdapter
from app.providers.ollama import HTTP_TLS_CONTEXT


def test_cache_enforces_bytes_count_expiry_and_metadata_isolation(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(cache.time, "monotonic", lambda: clock[0])
    store = SpeechCache(2, 8, 5)
    store.put("one", {"audio_bytes": b"ONE", "warnings": ["test-only"]})
    result = store.get("one")
    result["warnings"].append("changed")
    assert store.get("one")["warnings"] == ["test-only"]
    store.put("two", {"audio_bytes": b"TWO"})
    store.get("one")
    store.put("three", {"audio_bytes": b"THREE"})
    assert store.get("two") is None and store.bytes <= 8
    clock[0] = 16
    assert store.get("one") is None and store.get("three") is None
    assert store.bytes == 0


def test_oversized_audio_not_cached_and_invalid_bounds_rejected():
    store = SpeechCache(1, 3, 5)
    store.put("too_big", {"audio_bytes": b"TEST-ONLY"})
    assert store.get("too_big") is None and store.bytes == 0
    with pytest.raises(ValueError):
        SpeechCache(0, 3, 5)


def test_cache_key_changes_with_input_or_synthesis_policy(monkeypatch):
    key = runtime._speech_key("test-only text")
    assert key != runtime._speech_key("different text")
    assert key != runtime._speech_key("test-only text", voice_id=1)
    assert key != runtime._speech_key("test-only text", speed=1.2)
    monkeypatch.setitem(
        runtime.POLICY, "tts_threads", runtime.POLICY["tts_threads"] + 1
    )
    assert key != runtime._speech_key("test-only text")


def test_cache_never_bypasses_model_integrity_or_stop(monkeypatch, tmp_path):
    (tmp_path / "sherpa_onnx").mkdir()
    monkeypatch.setattr(runtime, "DEPENDENCIES", tmp_path)
    store = SpeechCache(1, 100, 5)
    store.put(runtime._speech_key("test-only"), {"audio_bytes": b"TEST-ONLY"})
    monkeypatch.setattr(runtime, "SPEECH_CACHE", store)

    def mismatch(*args, **kwargs):
        raise SireError("media_model_integrity", "TEST-ONLY model hash mismatch", 503)

    monkeypatch.setattr(runtime, "model_files", mismatch)
    with pytest.raises(SireError) as error:
        runtime.run("tts", {"text": "test-only"})
    assert error.value.code == "media_model_integrity"
    monkeypatch.setattr(runtime, "model_files", lambda *args: {})
    stop = threading.Event()
    stop.set()
    with pytest.raises(SireError) as error:
        runtime.run("tts", {"text": "test-only"}, cancel_event=stop)
    assert error.value.code == "media_cancelled"


def test_reused_trust_context_keeps_certificate_and_hostname_verification():
    assert HTTP_TLS_CONTEXT.verify_mode == ssl.CERT_REQUIRED
    assert HTTP_TLS_CONTEXT.check_hostname
    assert HTTP_TLS_CONTEXT.get_ca_certs()


def test_evidence_output_budget_is_scoped_without_expanding_plain_conversation():
    """External-source comparison has room to finish without slowing harmless chat."""
    from app.core.config import SETTINGS

    provider = OllamaAdapter()
    assert (
        provider.for_profile("evidence").text_budget
        == SETTINGS["evidence_output_tokens"]
    )
    assert (
        provider.for_profile("conversation").text_budget
        == SETTINGS["conversation_output_tokens"]
    )
    assert (
        provider.for_profile("plain").text_budget
        < provider.for_profile("evidence").text_budget
    )


def test_model_discovery_does_not_block_the_async_request_loop(monkeypatch):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    provider = OllamaAdapter()

    def discovery():
        entered.set()
        try:
            release.wait(3)
            return []
        finally:
            finished.set()

    monkeypatch.setattr(provider, "list_models", discovery)

    async def exercise():
        stream = provider.stream([], "test-only-absent-model", asyncio.Event())
        task = asyncio.create_task(anext(stream))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            assert (
                not finished.is_set()
            ), "Synchronous discovery blocked the request loop"
            release.set()
            with pytest.raises(SireError) as error:
                await task
            assert error.value.code == "model_missing"
        finally:
            release.set()
            await stream.aclose()

    asyncio.run(exercise())
