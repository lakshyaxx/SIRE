"""Real report bytes and canonical vision cache/provenance boundaries with test-only transport."""

import asyncio
import io
from PIL import Image
from pypdf import PdfReader
from app.chat.vision import inspect
from app.chat.service import ChatService
from app.core.config import SETTINGS
from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.knowledge.ingestion import ingest
from app.orchestration.runtime import Runner, Plan
from app.orchestration.tools import build_registry
from app.reports.evidence_case import create
from app.reports.engineering import pdf_bytes


def test_uploaded_case_report_preserves_source_and_does_not_claim_simulated_plant(
    store,
):
    cid = store.create_conversation()["id"]
    ingest(
        store,
        cid,
        "test-only-inspection.txt",
        b"Test-only inspection note: independent examination is missing.",
    )
    source_id = store.rows("SELECT id FROM chunks")[0]["id"]
    saved = {
        "case": {
            "question": "| test-only untrusted question |",
            "conversation_id": cid,
            "evidence": [{"id": source_id}],
        },
        "hypotheses": [],
        "tools": [],
        "unresolved": ["Independent examination missing"],
        "limitations": ["Test-only unverified source"],
        "stop_reason": "insufficient_evidence",
    }
    identifier = store.save_result("cases", saved, cid)
    report = create(Ledger(store), identifier)
    assert report == create(Ledger(store), identifier)
    pdf = pdf_bytes(report)
    assert pdf == pdf_bytes(report)
    text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    assert "uploaded-evidence" in text and "SIMULATED FACILITY" not in text
    assert identifier in text and "independent examination" in text


def test_vision_cache_binds_actual_model_digest_and_question(
    store, provider, monkeypatch
):
    cid = store.create_conversation()["id"]
    data = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(data, format="PNG")
    item = ingest(store, cid, "test-only-image.png", data.getvalue())
    calls = []
    monkeypatch.setattr(
        provider,
        "list_models",
        lambda: [{"name": SETTINGS["vision_model"], "digest": "test-only-digest"}],
    )

    async def vision(content, question):
        calls.append(question)
        return {
            "provider": "test-only",
            "model": SETTINGS["vision_model"],
            "visible_observations": ["Test-only observation for " + question],
            "limitations": ["Test fixture, no actual visual diagnostic claim"],
        }

    monkeypatch.setattr(provider, "vision", vision)

    async def run():
        runner = Runner(
            Ledger(store),
            Plan(intent="test-only", goals=[], tools=[]),
            build_registry(store, provider),
        )
        one = await inspect(
            store,
            provider,
            runner,
            store.attachment(item["id"]),
            "test-only question one",
            asyncio.Event(),
        )
        again = await inspect(
            store,
            provider,
            runner,
            store.attachment(item["id"]),
            "test-only question one",
            asyncio.Event(),
        )
        other = await inspect(
            store,
            provider,
            runner,
            store.attachment(item["id"]),
            "test-only question two",
            asyncio.Event(),
        )
        assert again["tool"]["status"] == "cached"
        assert (
            one["evidence"][0].id == again["evidence"][0].id != other["evidence"][0].id
        )
        assert (
            Ledger(store)
            .resolve(other["evidence"][0].id)["evidence"]["observation"]["observation"]
            .endswith("question two")
        )

    asyncio.run(run())
    assert len(calls) == 2


def test_failed_vision_keeps_actual_document_evidence_and_partial_status(
    store, provider, monkeypatch
):
    cid = store.create_conversation()["id"]
    data = io.BytesIO()
    Image.new("RGB", (4, 4)).save(data, format="PNG")
    image = ingest(store, cid, "test-only.png", data.getvalue())
    document = ingest(
        store,
        cid,
        "test-only.txt",
        b"Test-only pressure inspection record requires independent verification.",
    )

    async def unavailable(*args):
        raise SireError(
            "test_only_vision_outage", "Test-only unavailable provider", 503
        )

    monkeypatch.setattr(provider, "vision", unavailable)

    async def run():
        return [
            event
            async for event in ChatService(store, provider).events(
                cid,
                "test-only-job",
                "Summarize the pressure inspection record and visible features",
                [image["id"], document["id"]],
                "chat",
                None,
                None,
                False,
            )
        ]

    events = asyncio.run(run())
    assert events[-1]["status"] == "partial"
    assert any(
        item["modality"] == "document" for item in events[-1]["metadata"]["evidence"]
    )
    assert events[-1]["metadata"]["tool_errors"][0]["code"] == "test_only_vision_outage"
    metadata = events[-1]["metadata"]
    trace = Ledger(store).get("runs", metadata["orchestration"]["run_id"])
    retrieval = next(
        step for step in trace["steps"] if step["tool_id"] == "knowledge.retrieve"
    )
    assert retrieval["input_evidence_ids"] == [document["id"]]
    assert set(retrieval["output_evidence_ids"]) == {
        item["id"] for item in metadata["evidence"] if item["modality"] == "document"
    }


def test_natural_report_request_dispatches_actual_export_without_model(v2client):
    import json

    store = v2client.app.state.store
    cid = store.create_conversation()["id"]
    ingest(
        store,
        cid,
        "test-only.txt",
        b"Test-only stored source requiring independent inspection.",
    )
    source_id = store.rows("SELECT id FROM chunks")[0]["id"]
    saved = {
        "case": {
            "question": "Test-only",
            "conversation_id": cid,
            "evidence": [{"id": source_id}],
        },
        "hypotheses": [],
        "tools": [],
        "unresolved": ["Missing independent inspection"],
        "limitations": ["Test-only"],
        "stop_reason": "insufficient_evidence",
    }
    identifier = store.save_result("cases", saved, cid)
    response = v2client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": cid,
            "content": "Export this investigation report as PDF",
        },
    )
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert events[-1]["status"] == "complete"
    assert events[-1]["metadata"]["generic_report"]["case_id"] == identifier
    trace = v2client.get(
        "/api/v1/runs/" + events[-1]["metadata"]["orchestration"]["run_id"] + "/trace"
    ).json()
    assert [step["tool_id"] for step in trace["steps"]] == ["evidence_case.report"]
