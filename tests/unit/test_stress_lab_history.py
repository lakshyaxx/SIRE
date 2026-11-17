"""Source-backed history routing and immutable revision/reference safety regressions."""

import asyncio
import json
import pytest
from app.chat.service import ChatService
from app.evidence.ledger import Ledger
from app.simulation.generator import seed_scenarios
from app.simulation.repository import Observations


def test_cooperative_stop_emits_done_and_releases_scoped_turn(store):
    seed_scenarios(store.path.parent / "scenarios", 42, [0])
    scenario = Observations(store.path.parent / "scenarios").scenarios()[0]

    async def run():
        cid = store.create_conversation("Test-only cooperative stop")["id"]
        service = ChatService(store)
        stream = service.events(
            cid,
            "test-stop",
            "Investigate this fault",
            [],
            "chat",
            None,
            None,
            False,
            context={
                "scenario_id": scenario["id"],
                "asset_id": scenario["asset_id"],
                "as_of": scenario["reference_at"],
            },
        )
        assert (await anext(stream))["type"] == "started"
        assert (await anext(stream))["type"] == "plan"
        assert service.cancel("test-stop")
        events = [event async for event in stream]
        assert events[-1]["type"] == "done" and events[-1]["status"] == "cancelled"
        assert store.messages(cid)[-1]["status"] == "cancelled"
        assert not service.jobs and not service.active_conversations

    asyncio.run(run())


def test_actual_task_cancellation_propagates_even_when_stop_was_requested(
    store, provider, monkeypatch
):
    async def run():
        entered = asyncio.Event()

        async def blocked(*args):
            entered.set()
            await asyncio.Future()
            yield "unreachable test-only token"

        monkeypatch.setattr(provider, "stream", blocked)
        cid = store.create_conversation("Test-only task cancellation")["id"]
        service = ChatService(store, provider)

        async def consume():
            return [
                event
                async for event in service.events(
                    cid,
                    "task-stop",
                    "Tell me a short story",
                    [],
                    "chat",
                    None,
                    None,
                    False,
                )
            ]

        task = asyncio.create_task(consume())
        await asyncio.wait_for(entered.wait(), 2)
        assert service.cancel("task-stop")
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert store.messages(cid)[-1]["status"] == "cancelled"
        assert not service.jobs and not service.active_conversations

    asyncio.run(run())


def post(client, cid, question, context):
    """Exercise actual SSE and return the final stored metadata/events."""
    response = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": cid, "content": question, "context": context},
    )
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert events[-1]["status"] == "complete", events
    return events, events[-1]["metadata"]


def test_onset_abstains_instead_of_inventing_a_point_and_revisit_links_parent(v2client):
    store = v2client.app.state.store
    seed_scenarios(store.path.parent / "scenarios", 42, [0])
    scenario = Observations(store.path.parent / "scenarios").scenarios()[0]
    context = {
        "scenario_id": scenario["id"],
        "asset_id": scenario["asset_id"],
        "as_of": scenario["reference_at"],
    }
    cid = v2client.post("/api/v1/conversations", json={}).json()["id"]
    _, first = post(v2client, cid, "Investigate this fault", context)
    case = first["workspace"]["outputs"]["facility.investigate"]["case"]
    before = Ledger(store).get("cases", case["id"])
    events, onset = post(
        v2client,
        cid,
        "What was the earliest credible anomaly?",
        first["workspace"]["context"],
    )
    answer = "".join(
        event.get("text", "") for event in events if event["type"] == "delta"
    )
    assert "Earliest abnormal sample not established" in answer
    assert set(onset["workspace"]["outputs"]) == {"temporal.summary", "events.timeline"}
    assert onset["model_activity"] == []
    _, revised = post(
        v2client, cid, "Revisit this saved case", first["workspace"]["context"]
    )
    child = revised["workspace"]["outputs"]["facility.investigate"]["case"]
    assert child["id"] != case["id"] and child["parent_case_id"] == case["id"]
    assert child["revision_source_status"] == "same_evidence_snapshot"
    assert Ledger(store).get("cases", case["id"]) == before


def test_history_only_unknown_alias_is_buffered_and_withheld(
    store, provider, monkeypatch
):
    cid = store.create_conversation("Test-only historical citation")["id"]
    record = Ledger(store).add(
        "manually_entered",
        "Test-only history",
        {"claim": "Unverified test-only claim"},
        {"test_only": True},
    )
    store.add_message(
        cid,
        "assistant",
        "Test-only previous source [" + record.id + "]",
        metadata={"workspace": {"evidence_ids": [record.id]}},
    )

    async def invalid(*args):
        yield "Test-only fabricated reference [E1]"

    monkeypatch.setattr(provider, "stream", invalid)

    async def run():
        return [
            event
            async for event in ChatService(store, provider).events(
                cid,
                "test-only-history-job",
                "Explain the preceding result",
                [],
                "chat",
                None,
                None,
                False,
            )
        ]

    events = asyncio.run(run())
    assert events[-1]["status"] == "error"
    assert events[-1]["metadata"]["error"]["code"] == "unsupported_source_reference"
    assert not any(event["type"] == "delta" for event in events)
