"""Pump release regression using explicit unit fixtures; real-case replay is separate."""

import asyncio
import csv
import io
from statistics import mean

import pytest

from app.core.errors import SireError
from app.evidence.measurements import parse, profile
from app.investigation.jobs import InvestigationJob, InvestigationJobs
from app.knowledge.ingestion import ingest
from app.orchestration.planner import nasa_command, rul_requested
from app.storage.database import now
from app.evidence.inventory import check_absence


def test_generic_csv_absence_cannot_hide_actual_uploaded_measurements():
    available = [
        {
            "asset_id": "UNIT-017",
            "channel": "vibration",
            "unit": "mm/s RMS",
            "good_count": 24,
            "evidence_id": "unit-measurement",
        }
    ]
    corrected, checks = check_absence(
        [
            "No quantitative data from the CSV is available for analysis, so trend magnitude cannot be verified."
        ],
        available,
        "UNIT-017",
    )
    assert checks[0]["status"] == "contradicted"
    assert "24 good rows" in corrected[0] and "[unit-measurement]" in corrected[0]
    assert "sufficiency remains unverified" in corrected[0]


@pytest.mark.parametrize(
    "text",
    [
        "No data is available for lubricant viscosity.",
        "No sensor data is available for OTHER-999.",
    ],
)
def test_csv_availability_does_not_invent_missing_channel_or_other_asset_data(text):
    available = [
        {
            "asset_id": "UNIT-017",
            "channel": "vibration",
            "unit": "mm/s RMS",
            "good_count": 24,
            "evidence_id": "unit-measurement",
        }
    ]
    corrected, checks = check_absence([text], available, "UNIT-017")
    assert corrected == [text] and checks[0]["status"] == "unverified"


@pytest.mark.parametrize(
    "question",
    [
        "Investigate PUMP-017. Do not calculate unsupported remaining useful life.",
        "Do not assume a confirmed cause, calculate remaining useful life, or suggest operating changes.",
        "Diagnose this pump without estimating RUL.",
        "Never estimate RUL from a photograph.",
        "I don't want you to estimate RUL. Investigate the fault.",
        "Explain what RUL means.",
    ],
)
def test_exclusions_are_not_rul_commands(question):
    assert not rul_requested(question)


@pytest.mark.parametrize(
    "question",
    [
        "Estimate remaining useful life from this photograph.",
        "Calculate RUL using this generic CSV.",
        "Do not confirm a cause, but estimate remaining useful life.",
        "Do not estimate pressure; calculate RUL.",
        "Without assuming a root cause, estimate remaining useful life.",
        "No measurements are available, calculate RUL.",
    ],
)
def test_affirmative_rul_requests_still_require_real_prediction_inputs(question):
    assert rul_requested(question)


def test_negated_nasa_commands_never_load_models():
    assert nasa_command("Do not predict RUL for FD001 engine 1") is None
    assert nasa_command("Predict FD001 engine 1")["asset_id"] == "FD001-ENGINE-001"


def unit_csv(quality: str = "OK") -> bytes:
    """Build an explicitly test-only unit file with the real header variants."""
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        [
            "timestamp_utc",
            "asset_id",
            "vibration_mm_s_rms",
            "bearing_temp_c",
            "discharge_pressure_bar",
            "suction_pressure_bar",
            "flow_m3_h",
            "motor_current_a",
            "speed_rpm",
            "quality_flag",
        ]
    )
    for index in range(24):
        writer.writerow(
            [
                f"2026-01-01T{index:02d}:00:00Z",
                "UNIT-017",
                index + 1,
                40 + index,
                5 - index / 100,
                2,
                50 - index / 10,
                10 + index / 100,
                1480,
                quality,
            ]
        )
    return stream.getvalue().encode()


def test_wide_headers_quality_and_statistics_are_exact_without_nasa(store):
    cid = store.create_conversation()["id"]
    data = unit_csv()
    rows = parse(data, ".csv")
    assert len(rows) == 168
    assert {row["channel"] for row in rows} == {
        "vibration",
        "bearing_temp",
        "downstream_pressure",
        "upstream_pressure",
        "flow",
        "current",
        "speed",
    }
    assert {row["quality"] for row in rows} == {"good"}
    assert {row["source_quality"] for row in rows} == {"OK"}
    item = ingest(store, cid, "explicit-unit-pump.csv", data)
    assert not item["metadata"]["prediction_eligible"]
    result = profile(store, cid, item["id"])
    vibration = next(g for g in result["groups"] if g["channel"] == "vibration")
    assert vibration["count"] == 24
    assert vibration["baseline_mean"] == mean(range(1, 25))
    assert vibration["recent_mean"] == mean(range(19, 25))
    assert vibration["delta"] == 9
    assert vibration["baseline_window"]["start"] == "2026-01-01T00:00:00+00:00"
    assert vibration["recent_window"]["end"] == "2026-01-01T23:00:00+00:00"
    assert not store.rows("SELECT * FROM predictions")


def test_unknown_quality_never_becomes_good_or_imputed(store):
    cid = store.create_conversation()["id"]
    item = ingest(store, cid, "explicit-unit-bad.csv", unit_csv("BAD"))
    with pytest.raises(SireError, match="No good-quality"):
        profile(store, cid, item["id"])


def test_non_cmapss_negative_rul_investigation_reaches_measurements(store, provider):
    from app.chat.service import ChatService

    cid = store.create_conversation()["id"]
    item = ingest(store, cid, "explicit-unit-pump.csv", unit_csv())

    async def run():
        stream = ChatService(store, provider).events(
            cid,
            "unit-negative-rul",
            "Investigate UNIT-017 using attached evidence. Do not assume a cause, calculate unsupported remaining useful life, or recommend changes.",
            [item["id"]],
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
                break
        await stream.aclose()
        return seen

    events = asyncio.run(run())
    assert any(
        e.get("tool") == "measurements.profile" and e["status"] == "complete"
        for e in events
    )
    assert not provider.requests and not store.rows("SELECT * FROM predictions")


def test_worker_exception_is_sanitized_terminal_and_keeps_submitted_context(
    store, provider, monkeypatch
):
    from app.chat.service import ChatService

    cid = store.create_conversation()["id"]
    item = ingest(store, cid, "explicit-unit.txt", b"Explicit unit source")

    async def fail(self, **request):
        raise RuntimeError("PRIVATE_SOURCE_PATH_MUST_NOT_LEAK")
        yield

    monkeypatch.setattr(ChatService, "events", fail)

    async def run():
        manager = InvestigationJobs(store, provider)
        body = {
            "conversation_id": cid,
            "request_id": "unit-worker-failure",
            "content": "Investigate UNIT-017",
            "attachment_ids": [item["id"]],
        }
        job = manager.submit(body)
        await asyncio.gather(*list(manager.tasks.values()))
        return manager.get(job.id, cid)

    saved = asyncio.run(run())
    assert saved.status == "error" and saved.error["stage"] == "job_worker"
    assert (
        "RuntimeError" in saved.error["message"]
        and "PRIVATE_SOURCE" not in saved.error["message"]
    )
    assert saved.request["attachment_ids"] == [item["id"]]
    assert saved.request["content"] == "Investigate UNIT-017"


def test_missing_and_cross_conversation_attachments_are_rejected_before_job_creation(
    v2client,
):
    store = v2client.app.state.store
    cid = store.create_conversation()["id"]
    other = store.create_conversation()["id"]
    item = ingest(store, other, "explicit-unit.txt", b"Explicit unit source")
    for identifiers in (["missing-unit-id"], [item["id"]], []):
        response = v2client.post(
            "/api/v1/investigation-jobs",
            json={
                "conversation_id": cid,
                "content": "Investigate the attached files",
                "attachment_ids": identifiers,
            },
        )
        assert response.status_code in (404, 422)
    assert not store.rows("SELECT * FROM v45_jobs")


def test_legacy_failed_job_projects_real_attachments_asset_and_error_without_writing(
    v2client,
):
    store = v2client.app.state.store
    cid = store.create_conversation()["id"]
    item = ingest(store, cid, "explicit-unit.txt", b"Explicit unit maintenance record")
    user = store.add_message(
        cid,
        "user",
        "Investigate UNIT-017 using attached files",
        metadata={"attachments": [item["id"]]},
    )
    job = InvestigationJob(
        id="unit-legacy-failure",
        conversation_id=cid,
        request_id="unit-legacy-request",
        created_at=now(),
        updated_at=now(),
        status="error",
        events=[{"type": "started", "user_message_id": user}],
        error={
            "code": "rul_requires_sensor_tool",
            "message": "Explicit unit routing failure",
        },
    )
    with store.connection() as db:
        db.execute(
            "INSERT INTO v45_jobs VALUES(?,?,?,?,?)",
            (job.id, cid, job.request_id, "unit-hash", job.model_dump_json()),
        )
    before = store.rows("SELECT * FROM v45_jobs")
    response = v2client.get("/api/v1/frontend/investigations/" + job.id)
    assert response.status_code == 200
    record = response.json()
    assert (
        record["requested_asset_id"] == "UNIT-017"
        and record["asset_identity_source"] == "user_question"
    )
    assert record["attachment_ids"] == [item["id"]]
    assert record["attachments"][0]["name"] == "explicit-unit.txt"
    assert (
        record["failure"]["stage"] == "routing"
        and record["failure"]["message"] == "Explicit unit routing failure"
    )
    assert store.rows("SELECT * FROM v45_jobs") == before
