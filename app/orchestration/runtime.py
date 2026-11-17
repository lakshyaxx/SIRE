"""Typed internal plans, bounded specialist dispatch and privacy-safe operational traces."""

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import SireError
from app.evidence.ledger import Ledger, digest
from app.storage.database import now
from app.orchestration.cancellation import run_cancellable


class Invocation(BaseModel):
    """One validated tool request, with explicit prerequisites."""

    model_config = ConfigDict(extra="forbid")
    tool_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    """Auditable routing decisions; never a transcript of hidden model reasoning."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent: str
    goals: list[str]
    tools: list[Invocation]
    evidence_ids: list[str] = Field(default_factory=list)
    allowed_external_providers: list[str] = Field(default_factory=list)
    deadline_seconds: float = Field(default=90, gt=0, le=300)
    max_tool_calls: int = Field(default=12, ge=1, le=20)
    fallback: str = (
        "Return explicit partial/error status; never fabricate tool findings."
    )


class ToolSpec(BaseModel):
    """Serializable capability metadata paired with a real adapter at registration."""

    tool_id: str
    version: str = "1"
    input_schema: dict
    output_schema: dict = Field(default_factory=lambda: {"type": "object"})
    data_permissions: list[str] = Field(default_factory=lambda: ["local_only"])
    supported_input_types: list[str]
    requires_gpu: bool = False
    estimated_cost: float = 0
    timeout_s: float = 60
    availability: str = "available"
    expected_latency: str = "unprofiled; measured per call"
    error_types: list[str] = Field(
        default_factory=lambda: ["unsupported", "timeout", "invalid_input"]
    )
    source_provenance_policy: str = (
        "Resolvable input/output evidence IDs; interpretation is not measurement."
    )


class Registry:
    """Whitelist callable tools and validate typed arguments before every invocation."""

    def __init__(self) -> None:
        self.tools: dict[
            str, tuple[ToolSpec, type[BaseModel], Callable[..., Awaitable[dict]]]
        ] = {}

    def register(
        self,
        tool_id: str,
        schema: type[BaseModel],
        adapter: Callable[..., Awaitable[dict]],
        input_types: list[str],
        timeout: float = 60,
    ) -> None:
        """Register exactly one actual adapter per stable capability ID."""
        if tool_id in self.tools:
            raise ValueError("Duplicate capability")
        self.tools[tool_id] = (
            ToolSpec(
                tool_id=tool_id,
                input_schema=schema.model_json_schema(),
                supported_input_types=input_types,
                timeout_s=timeout,
            ),
            schema,
            adapter,
        )


class Runner:
    """Enforce per-tool/total budgets, deduplication, cancellation and durable traces."""

    def __init__(
        self, ledger: Ledger, plan: Plan, registry: Registry | None = None
    ) -> None:
        self.ledger, self.plan, self.registry = ledger, plan, registry or Registry()
        self.id = str(uuid.uuid4())
        self.started = time.monotonic()
        public_plan = plan.model_dump()
        for call in public_plan["tools"]:
            call["arguments"] = {"sha256": digest(call["arguments"])}
        self.trace: dict = {
            "id": self.id,
            "plan": public_plan,
            "started_at": now(),
            "steps": [],
            "status": "running",
            "network": "local_only",
        }
        self.cache: dict[str, dict] = {}
        self._save()

    def _save(self) -> None:
        self.ledger.save("runs", self.trace, self.id)

    @asynccontextmanager
    async def span(
        self, tool_id: str, input_ids: list[str] | None = None
    ) -> AsyncIterator[dict]:
        """Record an actual externally streamed or internally dispatched tool execution."""
        if len(self.trace["steps"]) >= self.plan.max_tool_calls:
            raise SireError("tool_budget", "Tool-call budget exhausted.", 429)
        remaining = self.plan.deadline_seconds - (time.monotonic() - self.started)
        if remaining <= 0:
            raise SireError("run_timeout", "Run time budget exhausted.", 503)
        step = {
            "tool_id": tool_id,
            "started_at": now(),
            "input_evidence_ids": input_ids or [],
            "output_evidence_ids": [],
            "status": "running",
            "warnings": [],
            "network": "local_only",
        }
        self.trace["steps"].append(step)
        self._save()
        start = time.monotonic()
        try:
            async with asyncio.timeout(remaining):
                yield step
            if step["status"] == "running":
                step["status"] = "ok"
        except (asyncio.CancelledError, GeneratorExit):
            step["status"] = "cancelled"
            raise
        except TimeoutError as exc:
            step["status"] = "error"
            step["error"] = {
                "code": "tool_timeout",
                "detail": "Tool or total time budget reached.",
            }
            raise SireError(
                "tool_timeout", "The local tool reached its time budget.", 503
            ) from exc
        except Exception as exc:
            step["status"] = "error"
            step["error"] = {
                "code": getattr(exc, "code", "tool_error"),
                "detail": "Tool did not complete; no substituted output.",
            }
            raise
        finally:
            step["ended_at"] = now()
            step["elapsed_seconds"] = time.monotonic() - start
            self._save()

    async def execute(self, invocation: Invocation, cancelled: asyncio.Event) -> dict:
        """Dispatch only registered typed tools; reuse identical safe results within this run."""
        if cancelled.is_set():
            raise asyncio.CancelledError()
        if invocation.tool_id not in self.registry.tools:
            raise SireError("unknown_tool", "Requested tool is not registered.")
        spec, schema, adapter = self.registry.tools[invocation.tool_id]
        args = schema.model_validate(invocation.arguments)
        key = digest(
            [
                spec.tool_id,
                spec.version,
                args.model_dump(),
                self.plan.evidence_ids,
                spec.data_permissions,
            ]
        )
        if key in self.cache:
            return {**self.cache[key], "cache_hit": True}
        async with self.span(spec.tool_id, self.plan.evidence_ids) as step:
            result = await run_cancellable(adapter(args), cancelled, spec.timeout_s)
            if cancelled.is_set():
                raise asyncio.CancelledError()
            step["arguments_sha256"] = digest(args.model_dump())
            step["output_evidence_ids"] = result.get("evidence_ids", [])
            provenance = (
                result.get("analysis")
                or result.get("prediction")
                or result.get("transcript")
            )
            if provenance:
                step["model_provenance"] = {
                    "provider": provenance.get("provider", "native_cpu"),
                    "model": provenance.get("model", provenance.get("model_id")),
                    "digest": provenance.get("model_digest")
                    or provenance.get("provenance", {}).get("version"),
                }

            self.cache[key] = result
            return result

    def finish(self, status: str) -> None:
        """Close an observed run with explicit completion/partial/cancellation status."""
        self.trace.update(
            status=status,
            ended_at=now(),
            elapsed_seconds=time.monotonic() - self.started,
        )
        self._save()


def chat_plan(
    content: str,
    attachment_kinds: list[str],
    investigation: bool,
    prediction_id: str | None,
) -> Plan:
    """Route obvious input modalities deterministically, without expensive greeting tools."""
    from app.orchestration.planner import nasa_command

    nasa = nasa_command(content) if not prediction_id and not investigation else None
    if nasa:
        return Plan(
            intent="rul_prediction",
            goals=[
                "Run the explicitly requested NASA simulation model, then explain its actual output"
            ],
            tools=[
                Invocation(tool_id="prediction.run", arguments=nasa),
                Invocation(tool_id="llm.chat"),
            ],
            deadline_seconds=300,
        )
    tools = []
    if "video" in attachment_kinds:
        tools.append(Invocation(tool_id="video.frames"))
        tools.append(Invocation(tool_id="vision.inspect"))
    if "audio" in attachment_kinds:
        tools.append(Invocation(tool_id="audio.transcript"))
    if "image" in attachment_kinds:
        tools.append(Invocation(tool_id="vision.inspect"))
    if any(k in attachment_kinds for k in ["document", "csv"]):
        tools.append(Invocation(tool_id="knowledge.retrieve"))
    if prediction_id:
        tools.append(Invocation(tool_id="prediction.saved_result"))
    tools.append(
        Invocation(tool_id="hypotheses.investigate" if investigation else "llm.chat")
    )
    intent = (
        "incident_investigation"
        if investigation
        else (
            "visual_inspection"
            if "image" in attachment_kinds
            else "knowledge_query" if attachment_kinds else "general_chat"
        )
    )
    return Plan(
        intent=intent,
        goals=["Answer using supplied evidence and actual local tools"],
        tools=tools,
        deadline_seconds=300,
    )
