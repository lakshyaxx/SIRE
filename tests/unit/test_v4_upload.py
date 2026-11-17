"""Actual intake receipts, scoped idempotence and explicit measurement contracts; test-only bytes."""

import hashlib
import pytest
from app.knowledge.ingestion import ingest
from app.evidence.ledger import Ledger
from app.evidence.measurements import parse, profile
from app.core.errors import SireError
import json


def test_receipt_is_durable_and_retry_deduplicates_only_inside_its_conversation(store):
    first = store.create_conversation()["id"]
    content = b"Explicit test-only maintenance note: verify the seal before inferring leakage."
    a = ingest(store, first, "test-only-note.txt", content)
    retry = ingest(store, first, "equivalent-test-only-name.txt", content)
    assert a["attachment_id"] == a["id"] == retry["id"] and retry["deduplicated"]
    assert a["ingestion_status"] == "ready" and a["size_bytes"] == len(content)
    assert a["metadata"]["original_sha256"] == hashlib.sha256(content).hexdigest()
    assert (
        Ledger(store).resolve(a["evidence_ids"][0])["evidence"]["pointer"][
            "attachment_id"
        ]
        == a["id"]
    )
    assert len(store.attachments(first)) == 1
    second = store.create_conversation()["id"]
    b = ingest(store, second, "test-only-note.txt", content)
    assert b["id"] != a["id"]
    with pytest.raises(SireError):
        store.attachment(a["id"], second)


def test_wide_header_units_preserve_values_and_original_row_field_without_nasa_eligibility(
    store,
):
    content = b"asset_id,timestamp_utc,vibration_mm_s,bearing_temp_c,synthetic\nTEST-ONLY,2026-01-01T03:00:00Z,2.685,65,true\nTEST-ONLY,2026-01-01T08:00:00Z,4.907,70,true\n"
    rows = parse(content, ".csv")
    assert rows[0]["value"] == 2.685 and rows[0]["source_row"] == 1
    assert rows[0]["source_field"] == "vibration_mm_s" and rows[0]["unit"] == "mm/s RMS"
    cid = store.create_conversation()["id"]
    item = ingest(store, cid, "test-only-wide.csv", content)
    assert item["metadata"]["prediction_eligible"] is False
    result = profile(store, cid, item["id"])
    assert result["synthetic_declared"] is True
    assert len(result["groups"]) == 2 and all(
        len(g["series"]) == 2 for g in result["groups"]
    )


def test_malformed_csv_width_and_non_image_bytes_are_controlled_errors(store):
    cid = store.create_conversation()["id"]
    for name, content in [
        ("test-only.csv", b"a,b\n1,2,3\n"),
        ("test-only.png", b"plain text is not an image"),
    ]:
        with pytest.raises(SireError):
            ingest(store, cid, name, content)
    assert store.attachments(cid) == []


def test_failed_database_commit_removes_only_the_new_unregistered_file(store):
    import sqlite3

    cid = store.create_conversation()["id"]
    with store.connection() as db:
        db.execute(
            "CREATE TRIGGER test_only_refuse BEFORE INSERT ON attachments BEGIN SELECT RAISE(ABORT, 'test only'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="test only"):
        ingest(
            store,
            cid,
            "test-only-note.txt",
            b"This test fixture must not remain orphaned.",
        )
    assert list((store.path.parent / "attachments").iterdir()) == []


def test_uploaded_statistics_question_uses_exact_tools_without_a_model(v2client):
    cid = v2client.post("/api/v1/conversations", json={}).json()["id"]
    content = b"asset_id,timestamp,channel,value,unit\nTEST-ONLY,2026-01-01T03:00:00Z,vibration,2.685,mm/s\nTEST-ONLY,2026-01-01T08:00:00Z,vibration,4.907,mm/s\n"
    upload = v2client.post(
        "/api/v1/attachments",
        data={"conversation_id": cid},
        files={"file": ("test-only.csv", content)},
    ).json()
    response = v2client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": cid,
            "content": "Summarize the exact statistics and units",
            "attachment_ids": [upload["id"]],
        },
    )
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert events[-1]["status"] == "complete"
    meta = events[-1]["metadata"]
    assert meta["response_route"] == "exact_uploaded_measurement_statistics"
    assert meta["model_activity"] == [] and meta["provider"] == "deterministic_tools"
    assert "not point measurements" in "".join(
        event.get("text", "") for event in events
    )
    assert meta["measurement_profiles"][0]["groups"][0]["recent_mean"] == pytest.approx(
        3.796, abs=1e-12
    )


def test_new_upload_cannot_enter_scoped_historical_answer(v2client):
    from app.simulation.generator import seed_scenarios, timestamp
    from app.simulation.repository import Observations

    store = v2client.app.state.store
    seed_scenarios(store.path.parent / "scenarios", 42, [0])
    scenario = Observations(store.path.parent / "scenarios").scenarios()[0]
    cid = store.create_conversation()["id"]
    uploaded = ingest(
        store,
        cid,
        "test-only-future.csv",
        b"asset_id,timestamp,channel,value,unit\nTEST-ONLY,2026-11-17T03:00:00Z,vibration,9876.543,mm/s\n",
    )
    response = v2client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": cid,
            "content": "Show historical vibration trend",
            "attachment_ids": [uploaded["id"]],
            "context": {
                "scenario_id": scenario["id"],
                "asset_id": scenario["asset_id"],
                "as_of": timestamp(72),
            },
        },
    )
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    meta = events[-1]["metadata"]
    assert events[-1]["status"] == "complete"
    assert meta["excluded_posthoc_evidence"]["attachment_ids"] == [uploaded["id"]]
    assert meta["provider"] == "deterministic_tools"
    assert "measurement_profiles" not in meta and meta["model_activity"] == []
    assert "9876.543" not in "".join(event.get("text", "") for event in events)
