"""V3 evidence integrity, typed dispatch, budget and privacy regression checks."""

import asyncio
import sqlite3
import pytest
from app.evidence.ledger import Ledger
from app.orchestration.runtime import Invocation, Plan, Registry, Runner, chat_plan
from app.orchestration.tools import build_registry


def test_append_only_sources_and_exact_resolver(store):
    ledger = Ledger(store)
    row = ledger.add(
        "manually_entered",
        "test-only note",
        {"text": "Untrusted inspection claim"},
        {"line": 1},
        available_at="2026-01-01T00:00:00+00:00",
    )
    assert (
        ledger.resolve(row.id)["evidence"]["observation"]["text"]
        == "Untrusted inspection claim"
    )
    with store.connection() as db, pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE v3_evidence SET payload='{}'")
    with pytest.raises(Exception, match="not found"):
        ledger.resolve("invented")


def test_v2_document_sources_resolve_without_changing_old_ids(store):
    from app.knowledge.ingestion import ingest

    c = store.create_conversation("Test-only source bridge")
    ingest(
        store,
        c["id"],
        "test-only.txt",
        b"Actual parser source text for a test-only claim.",
    )
    chunk = store.rows("SELECT id FROM chunks")[0]["id"]
    resolved = Ledger(store).resolve(chunk)
    assert resolved["requested_alias"] == chunk and resolved["evidence"][
        "id"
    ].startswith("EV:")
    assert (
        resolved["evidence"]["observation"]["excerpt"]
        == "Actual parser source text for a test-only claim."
    )


def test_raw_image_attachment_alias_is_source_metadata_not_a_visual_claim(store):
    import io
    from PIL import Image
    from app.knowledge.ingestion import ingest

    content = io.BytesIO()
    Image.new("RGB", (3, 3), "blue").save(content, format="PNG")
    conversation = store.create_conversation("Test-only image source")
    attachment = ingest(store, conversation["id"], "test-only.png", content.getvalue())
    resolved = Ledger(store).resolve(attachment["id"])
    assert resolved["requested_alias"] == attachment["id"]
    assert resolved["source"]["source_type"] == "real_uploaded"
    assert resolved["source"]["sha256"] == attachment["sha256"]
    assert (
        resolved["evidence"]["observation"]["mime"]
        == attachment["mime"]
        == "image/jpeg"
    )
    assert (
        resolved["evidence"]["extraction_method"]
        == "attachment_metadata_snapshot_not_model_observation"
    )
    assert (
        Ledger(store).resolve(attachment["id"])["evidence"]["id"]
        == resolved["evidence"]["id"]
    )


def test_schema_migration_preserves_v2_and_is_idempotent(store):
    c = store.create_conversation("Retain me")
    store.add_message(c["id"], "user", "Private history")
    Ledger(store)
    Ledger(store)
    assert store.messages(c["id"])[0]["content"] == "Private history"
    assert len(store.rows("SELECT * FROM schema_version WHERE version=3")) == 1


def test_hello_plan_has_only_conversational_tool():
    p = chat_plan("Hello", [], False, None)
    assert p.intent == "general_chat" and [c.tool_id for c in p.tools] == ["llm.chat"]


def test_explicit_nasa_plan_has_scoped_real_model_selection():
    plan = chat_plan("Predict FD003 engine 42", [], False, None)
    assert plan.intent == "rul_prediction"
    args = plan.tools[0].arguments
    assert args["dataset"] == "FD003" and args["asset_id"] == "FD003-ENGINE-042"
    assert args["model_id"].startswith("fd003-")
    assert (
        chat_plan("Explain why predictions need a dataset", [], False, None).intent
        == "general_chat"
    )


def test_real_dispatch_dedup_and_private_trace(store):
    async def run():
        call = Invocation(
            tool_id="text.profile", arguments={"text": "Private test-only text"}
        )
        runner = Runner(
            Ledger(store),
            Plan(intent="sensor_analysis", goals=["test"], tools=[call]),
            build_registry(store),
        )
        one = await runner.execute(call, asyncio.Event())
        two = await runner.execute(call, asyncio.Event())
        runner.finish("complete")
        assert one["words"] == 3 and two["cache_hit"]
        assert len(runner.trace["steps"]) == 1
        assert "Private test-only text" not in str(runner.trace)
        assert runner.trace["steps"][0]["elapsed_seconds"] >= 0

    asyncio.run(run())


def test_cancelled_dispatch_does_not_call_tool(store):
    async def run():
        c = Invocation(tool_id="text.profile", arguments={"text": "test"})
        runner = Runner(
            Ledger(store),
            Plan(intent="test", goals=[], tools=[c]),
            build_registry(store),
        )
        event = asyncio.Event()
        event.set()
        with pytest.raises(asyncio.CancelledError):
            await runner.execute(c, event)
        assert not runner.trace["steps"]

    asyncio.run(run())


def test_genuine_api_specialist_and_trace(v2client):
    r = v2client.post(
        "/api/v1/intelligence/execute",
        json={
            "tool_id": "text.profile",
            "arguments": {"text": "actual parsed request"},
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["result"]["words"] == 3
    trace = v2client.get("/api/v1/runs/" + out["run_id"] + "/trace").json()
    assert trace["status"] == "complete" and trace["steps"][0]["status"] == "ok"


def test_fresh_case_read_does_not_require_a_prior_chat(v2client):
    response = v2client.get("/api/v1/cases")
    assert response.status_code == 200 and response.json()["cases"] == []


def test_saved_visual_observation_resolves_as_inference(store):
    c = store.create_conversation("Test-only image claim")
    claim = {
        "id": "test-image:visual:0",
        "kind": "model_inference",
        "source_id": "test-image",
        "observation": "Test-only model observation",
        "locator": "test-image.png",
        "limitations": ["Unverified"],
    }
    store.add_message(c["id"], "assistant", "Test-only", metadata={"evidence": [claim]})
    result = Ledger(store).resolve(claim["id"])
    assert result["evidence"]["source_type"] == "model_generated"
    assert result["evidence"]["observation"] == claim
    assert Ledger(store).resolve(result["evidence"]["id"]) == {
        key: value for key, value in result.items() if key != "requested_alias"
    }


def test_tool_timeout_persists_real_failure(store):
    from pydantic import BaseModel
    from app.core.errors import SireError

    class Empty(BaseModel):
        """A test-only tool with no arguments."""

    async def slow_tool(args):
        await asyncio.sleep(1)
        return {}

    async def run():
        registry = Registry()
        registry.register("test.slow", Empty, slow_tool, [], timeout=0.001)
        call = Invocation(tool_id="test.slow", arguments={})
        runner = Runner(
            Ledger(store), Plan(intent="test", goals=[], tools=[call]), registry
        )
        with pytest.raises(SireError, match="time budget"):
            await runner.execute(call, asyncio.Event())
        step = Ledger(store).get("runs", runner.id)["steps"][0]
        assert step["status"] == "error" and step["error"]["code"] == "tool_timeout"
        assert not runner.cache

    asyncio.run(run())
