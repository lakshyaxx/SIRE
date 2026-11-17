"""Durable lifecycle, duplicate prevention and same-conversation independence; explicit test providers."""

import asyncio
import pytest
from app.chat.service import ChatService
from app.core.errors import SireError
from app.investigation.jobs import InvestigationJob, InvestigationJobs
from app.orchestration.case_context import recall
from app.storage.database import now


def request(cid, identifier="test-only-request"):
    return dict(
        conversation_id=cid,
        request_id=identifier,
        content="Slow test-only question",
        attachment_ids=[],
        mode="chat",
        model=None,
        prediction_id=None,
        linked_asset=False,
    )


def test_background_request_does_not_lock_ordinary_conversation_and_deduplicates(
    store, provider
):
    cid = store.create_conversation()["id"]

    async def run():
        gate = asyncio.Event()
        original = provider.stream

        async def stream(messages, model, cancelled):
            if "Slow test-only" in messages[-1]["content"]:
                await gate.wait()
            async for token in original(messages, model, cancelled):
                yield token

        provider.stream = stream
        manager = InvestigationJobs(store, provider)
        job = manager.submit(request(cid))
        assert manager.submit(request(cid)).id == job.id
        await asyncio.sleep(0.01)
        ordinary = ChatService(store, provider)
        events = [
            e
            async for e in ordinary.events(
                cid, "test-only-foreground", "Hi", [], "chat", None, None, False
            )
        ]
        assert events[-1]["status"] == "complete"
        assert manager.get(job.id, cid).status == "running"
        with pytest.raises(SireError) as conflict:
            manager.submit({**request(cid), "content": "different test-only content"})
        assert conflict.value.code == "request_id_conflict"
        other = store.create_conversation()["id"]
        with pytest.raises(SireError):
            manager.get(job.id, other)
        gate.set()
        await asyncio.gather(*list(manager.tasks.values()))
        saved = manager.get(job.id, cid)
        assert (
            saved.status == "complete" and saved.run_id and saved.assistant_message_id
        )
        assert saved.events[-1]["type"] == "done"
        assert not manager.tasks and len(store.messages(cid)) == 4

    asyncio.run(run())


def test_queued_cancel_releases_capacity_and_restart_is_not_fabricated_completion(
    store, provider
):
    cid = store.create_conversation()["id"]

    async def run():
        manager = InvestigationJobs(store, provider)
        job = manager.submit(request(cid))
        assert manager.cancel(job.id, cid).status == "cancelled"
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not manager.tasks and not store.messages(cid)
        stale = InvestigationJob(
            id="test-only-stale",
            conversation_id=cid,
            request_id="test-only-stale",
            created_at=now(),
            updated_at=now(),
            status="running",
        )
        with store.connection() as db:
            db.execute(
                "INSERT INTO v45_jobs VALUES(?,?,?,?,?)",
                (
                    stale.id,
                    cid,
                    stale.request_id,
                    "test-only-digest",
                    stale.model_dump_json(),
                ),
            )
        restarted = InvestigationJobs(store, provider)
        assert restarted.get(stale.id, cid).status == "interrupted"
        assert restarted.get(stale.id, cid).error["code"] == "process_restarted"

    asyncio.run(run())


def test_http_background_uses_actual_scoped_tools_and_survives_reload(v2client):
    from app.simulation.generator import seed_scenarios, timestamp
    from app.simulation.repository import Observations

    store = v2client.app.state.store
    seed_scenarios(store.path.parent / "scenarios", 42, [0])
    scenario = Observations(store.path.parent / "scenarios").scenarios()[0]
    cid = store.create_conversation()["id"]
    body = {
        "conversation_id": cid,
        "request_id": "test-only-http-job",
        "content": "Investigate this simulated vibration history",
        "context": {
            "scenario_id": scenario["id"],
            "asset_id": scenario["asset_id"],
            "as_of": timestamp(72),
        },
    }
    response = v2client.post("/api/v1/investigation-jobs", json=body)
    assert response.status_code == 202
    job = response.json()

    # Block on the actual owned task, not a fabricated success/estimated completion.
    async def finish():
        await asyncio.gather(
            *list(v2client.app.state.investigation_jobs.tasks.values())
        )

    v2client.portal.call(finish)
    saved = v2client.get(
        f"/api/v1/investigation-jobs/{job['id']}", params={"conversation_id": cid}
    ).json()
    assert saved["status"] == "complete" and saved["assistant_message_id"]
    assert any(e.get("tool") == "facility.investigate" for e in saved["events"])
    assert (
        v2client.post("/api/v1/investigation-jobs", json=body).json()["id"] == job["id"]
    )
    assert len(v2client.get("/api/v1/conversations/" + cid).json()["messages"]) == 2


def test_recall_reports_recorded_status_and_keeps_conversations_separate(
    store, provider
):
    cid = store.create_conversation()["id"]
    case = {
        "case": {"conversation_id": cid, "evidence": []},
        "hypotheses": [
            {
                "mechanism": "Test-only bearing wear",
                "status": "tentative",
                "evidence_support": "low",
                "missing_tests": ["Independent inspection"],
                "supporting_evidence_ids": [],
                "contradicting_evidence_ids": [],
            }
        ],
    }
    identifier = store.save_result("cases", case, cid)

    async def run():
        service = ChatService(store, provider)
        return [
            e
            async for e in service.events(
                cid,
                "test-only-recall",
                "Why did you rule out bearing wear?",
                [],
                "chat",
                None,
                None,
                False,
            )
        ]

    events = asyncio.run(run())
    assert (
        events[-1]["status"] == "complete"
        and events[-1]["metadata"]["recalled_case_id"] == identifier
    )
    assert events[-1]["metadata"]["model_activity"] == [] and not provider.requests
    assert "not physically ruled out" in store.messages(cid)[-1]["content"]
    assert recall(store, store.create_conversation()["id"]) is None


def test_verified_measurement_facts_precede_visual_and_model_work(store, provider):
    import io
    from PIL import Image
    from app.knowledge.ingestion import ingest

    cid = store.create_conversation()["id"]
    image = io.BytesIO()
    Image.new("RGB", (2, 2)).save(image, format="PNG")
    photo = ingest(store, cid, "test-only.png", image.getvalue())
    measured = ingest(
        store,
        cid,
        "test-only.csv",
        b"asset_id,timestamp,channel,value,unit\nTEST-777,2026-01-01T00:00:00Z,flow,12,m3/h\nTEST-777,2026-01-01T01:00:00Z,flow,13,m3/h\n",
    )

    async def run():
        service = ChatService(store, provider)
        stream = service.events(
            cid,
            "test-only-early-facts",
            "Investigate this supplied evidence",
            [photo["id"], measured["id"]],
            "investigate",
            None,
            None,
            False,
        )
        seen = []
        async for event in stream:
            seen.append(event)
            if event["type"] == "delta":
                assert event["source"] == "validated_descriptive_measurement_statistics"
                assert (
                    "TEST-777" in event["text"]
                    and "not point measurements" in event["text"]
                )
                assert not any(e.get("tool") == "vision.inspect" for e in seen)
                break
        await stream.aclose()
        assert not service.jobs and not provider.requests

    asyncio.run(run())


@pytest.mark.parametrize(
    "question",
    ["What is the investigation progress?", "What are you doing right now?"],
)
def test_status_uses_actual_job_state_without_model_and_hides_facts_from_historical_scope(
    store, provider, question
):
    cid = store.create_conversation()["id"]
    InvestigationJobs(store, provider)
    saved = InvestigationJob(
        id="test-only-job-status",
        conversation_id=cid,
        request_id="test-only-progress",
        created_at=now(),
        updated_at=now(),
        status="running",
        events=[
            {
                "type": "delta",
                "source": "validated_descriptive_measurement_statistics",
                "text": "TEST_ONLY_POSTHOC_VALUE_9988",
            }
        ],
    )
    with store.connection() as db:
        db.execute(
            "INSERT INTO v45_jobs VALUES(?,?,?,?,?)",
            (saved.id, cid, saved.request_id, "test-only", saved.model_dump_json()),
        )

    async def run():
        service = ChatService(store, provider)
        return [
            e
            async for e in service.events(
                cid,
                "test-only-status-turn",
                question,
                [],
                "chat",
                None,
                None,
                False,
                context={
                    "scenario_id": "test-only-no-hidden-scenario",
                    "asset_id": "UNIT-777",
                    "as_of": "2026-01-01T00:00:00Z",
                },
            )
        ]

    events = asyncio.run(run())
    assert (
        events[-1]["status"] == "complete"
        and events[-1]["metadata"]["model_activity"] == []
    )
    answer = "".join(e.get("text", "") for e in events)
    assert "**running**" in answer and "9988" not in answer and not provider.requests


def test_auto_dispatch_preserves_saved_case_followups_and_exact_completion_id(v2client):
    store = v2client.app.state.store
    cid = store.create_conversation()["id"]
    case = {"case": {"conversation_id": cid, "evidence": []}, "hypotheses": []}
    store.save_result("cases", case, cid)
    response = v2client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": cid,
            "content": "Why did you rule out bearing wear?",
            "background_if_deep": True,
        },
    )
    assert response.status_code == 200 and response.headers["content-type"].startswith(
        "text/event-stream"
    )
    import json

    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert events[-1]["status"] == "complete"
    assert events[-1]["metadata"]["model_activity"] == [] and not store.rows(
        "SELECT * FROM v45_jobs"
    )
    assert events[-1]["assistant_message_id"] == store.messages(cid)[-1]["id"]
