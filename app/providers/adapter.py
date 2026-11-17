"""Provider interface and real Ollama token streaming, with one active local model."""

import asyncio
import time
import json
from collections.abc import AsyncIterator
from typing import Any, Protocol

import httpx

from app.core.config import SETTINGS
from app.core.errors import SireError
from app.providers import ollama
from app.providers.resources import SCHEDULER
from app.orchestration.cancellation import run_cancellable


async def _lines(
    response: httpx.Response, cancelled: asyncio.Event
) -> AsyncIterator[str]:
    """Interrupt a stalled upstream read when Stop arrives, not only after the next token."""
    iterator = response.aiter_lines()
    while True:
        try:
            yield await run_cancellable(
                anext(iterator), cancelled, SETTINGS["llm_timeout_seconds"]
            )
        except StopAsyncIteration:
            return


class ProviderAdapter(Protocol):
    """Boundary for local provider discovery, generation, vision and embeddings."""

    def health(self) -> dict[str, Any]: ...
    def list_models(self) -> list[dict[str, Any]]: ...
    async def stream(
        self, messages: list[dict], model: str, cancelled: asyncio.Event
    ) -> AsyncIterator[str]: ...
    async def chat(
        self, messages: list[dict], model: str, cancelled: asyncio.Event
    ) -> str: ...
    async def vision(self, content: bytes, question: str) -> dict: ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaAdapter:
    """Make actual loopback calls; no hosted fallback, fake tokens or invented readiness."""

    def __init__(self, text_budget: int | None = None) -> None:
        self.text_budget = text_budget or SETTINGS.get(
            "conversation_output_tokens", 384
        )
        self.metrics: dict[str, Any] = {}

    def for_profile(self, profile: str) -> "OllamaAdapter":
        """Bind per-turn budgets without mutating a shared provider during another request."""
        from app.chat.conversation import POLICY

        budget = (
            POLICY["plain_output_tokens"]
            if profile == "plain"
            else (
                SETTINGS.get("voice_output_tokens", 180)
                if profile == "voice"
                else (
                    SETTINGS["max_output_tokens"]
                    if profile == "detailed"
                    else SETTINGS.get("conversation_output_tokens", 384)
                )
            )
        )
        return OllamaAdapter(text_budget=budget)

    def health(self) -> dict[str, Any]:
        """Report actual service and configured-model availability."""
        return ollama.readiness()

    def list_models(self) -> list[dict[str, Any]]:
        """Return the real installed tags, sizes, digests and provider capabilities."""
        try:
            response = httpx.get(
                ollama._base() + "/api/tags",
                timeout=3,
                trust_env=False,
                verify=ollama.HTTP_TLS_CONTEXT,
            )
            response.raise_for_status()
            return response.json()["models"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise SireError(
                "provider_unavailable",
                "Local Ollama is unavailable; start the documented launcher.",
                503,
            ) from exc

    async def stream(
        self, messages: list[dict], model: str, cancelled: asyncio.Event
    ) -> AsyncIterator[str]:
        """Yield only tokens emitted by Ollama; close its HTTP stream on cancellation."""
        began = time.monotonic()
        self.metrics = {
            "prompt_characters": sum(len(row["content"]) for row in messages),
            "output_token_limit": self.text_budget,
        }
        async with SCHEDULER.async_lease(
            "conversation", cancelled=cancelled, priority=0, model=model
        ) as lease:
            self.metrics["queue_seconds"] = lease["queue_seconds"]
            names = {row["name"] for row in await asyncio.to_thread(self.list_models)}
            if model not in names:
                raise SireError(
                    "model_missing", "Selected local model is not installed.", 503
                )
            if not ollama.PROVIDER_LOCK.acquire(blocking=False):
                raise SireError(
                    "provider_busy",
                    "Another local model call is active; retry shortly.",
                    429,
                )
            try:
                async with httpx.AsyncClient(
                    timeout=SETTINGS["llm_timeout_seconds"],
                    trust_env=False,
                    verify=ollama.HTTP_TLS_CONTEXT,
                ) as client:
                    async with client.stream(
                        "POST",
                        ollama._base() + "/api/chat",
                        json={
                            "model": model,
                            "messages": messages,
                            "stream": True,
                            "think": False,
                            "keep_alive": SETTINGS["ollama_keep_alive_seconds"],
                            "options": {
                                "temperature": SETTINGS["temperature"],
                                "seed": SETTINGS["seed"],
                                "num_ctx": SETTINGS["context_length"],
                                "num_predict": self.text_budget,
                            },
                        },
                    ) as response:
                        response.raise_for_status()
                        async for line in _lines(response, cancelled):
                            if cancelled.is_set():
                                return
                            if not line:
                                continue
                            item = json.loads(line)
                            if "error" in item:
                                raise SireError(
                                    "provider_error",
                                    "Local model could not complete the response.",
                                    503,
                                )
                            token = item.get("message", {}).get("content", "")
                            if token:
                                self.metrics.setdefault(
                                    "first_token_seconds", time.monotonic() - began
                                )
                                yield token
                            if item.get("done"):
                                for key in [
                                    "load_duration",
                                    "prompt_eval_count",
                                    "prompt_eval_duration",
                                    "prompt_eval_cached_count",
                                    "eval_count",
                                    "eval_duration",
                                    "total_duration",
                                    "done_reason",
                                ]:
                                    if key in item:
                                        self.metrics[key] = item[key]
                                self.metrics["elapsed_seconds"] = (
                                    time.monotonic() - began
                                )
                                if item.get("done_reason") == "length":
                                    raise SireError(
                                        "response_limit",
                                        "Model response reached the configured limit; ask a shorter question.",
                                        503,
                                    )
                                break
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                raise SireError(
                    "provider_unavailable",
                    "Local model request failed or timed out.",
                    503,
                ) from exc
            finally:
                ollama.PROVIDER_LOCK.release()

    async def chat(
        self, messages: list[dict], model: str, cancelled: asyncio.Event
    ) -> str:
        """Collect an actual token stream for non-streaming callers."""
        return "".join(
            [token async for token in self.stream(messages, model, cancelled)]
        )

    async def vision(self, content: bytes, question: str) -> dict:
        """Run real structured image inference without blocking the API event loop."""
        return await ollama.analyze_image_async(content, question, "")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Call an installed configured embedding model; otherwise fail explicitly."""
        model = SETTINGS.get("embedding_model")
        if not model:
            raise SireError(
                "embedding_unavailable",
                "No embedding model configured; retrieval uses actual lexical matches.",
                503,
            )
        async with SCHEDULER.async_lease("embedding", model=model):
            async with httpx.AsyncClient(
                timeout=30, trust_env=False, verify=ollama.HTTP_TLS_CONTEXT
            ) as client:
                response = await client.post(
                    ollama._base() + "/api/embed",
                    json={"model": model, "input": texts, "keep_alive": 0},
                )
                response.raise_for_status()
                return response.json()["embeddings"]
