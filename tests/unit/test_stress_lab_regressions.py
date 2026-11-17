"""Reproduced stress defects using real SQLite/ledger operations and explicitly test-only readings."""

from datetime import datetime, timedelta, timezone
import json
import sqlite3
import asyncio
import pytest
from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.investigation.facility import rank
from app.simulation.repository import Observations
from app.simulation.settings import CONFIG
from app.simulation.what_if import compare
from app.temporal.analytics import summarize
from app.chat.service import ChatService
from app.assets.fleet import overview
from app.orchestration.workspace import plan_workspace


def history(tmp_path, count=5001):
    """Create a clearly test-only public history spanning more than one API page."""
    directory = tmp_path / "observations"
    directory.mkdir()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    stamps = [(start + timedelta(minutes=n)).isoformat() for n in range(count)]
    scenario = {
        "id": "test-only",
        "name": "SIMULATED external test-only",
        "generator_version": "test-only-external",
        "starts_at": stamps[0],
        "reference_at": stamps[-1],
        "ends_at": stamps[-1],
        "asset_id": "LUBE-009",
    }
    with sqlite3.connect(directory / "observations.sqlite3") as db:
        db.executescript(
            "CREATE TABLE scenarios(id TEXT,payload TEXT); CREATE TABLE assets(scenario_id TEXT,id TEXT,payload TEXT); CREATE TABLE telemetry(scenario_id TEXT,asset_id TEXT,channel TEXT,observed_at TEXT,available_at TEXT,value REAL,unit TEXT,quality TEXT,source_type TEXT);"
        )
        db.execute(
            "INSERT INTO scenarios VALUES(?,?)", ("test-only", json.dumps(scenario))
        )
        db.execute(
            "INSERT INTO assets VALUES(?,?,?)",
            (
                "test-only",
                "LUBE-009",
                json.dumps({"id": "LUBE-009", "asset_type": "LUBE"}),
            ),
        )
        db.executemany(
            "INSERT INTO telemetry VALUES(?,?,?,?,?,?,?,?,?)",
            [
                (
                    "test-only",
                    "LUBE-009",
                    "oil_pressure",
                    stamp,
                    stamp,
                    float(n),
                    "bar",
                    "good",
                    "sire_synthetic_scenario",
                )
                for n, stamp in enumerate(stamps)
            ],
        )
    return Observations(directory), scenario


def test_trend_analysis_reads_latest_page_instead_of_silently_truncating(
    tmp_path, store
):
    repo, scenario = history(tmp_path)
    result = summarize(
        repo, Ledger(store), "test-only", "LUBE-009", scenario["reference_at"]
    )
    channel = result["channels"]["oil_pressure"]
    assert channel["count"] == 5001
    assert channel["baseline_mean"] == 11.5
    assert channel["recent_mean"] == 4997.5
    assert channel["latest_observed_at"] == scenario["reference_at"]


def test_analysis_budget_refuses_partial_recent_claim(tmp_path, store, monkeypatch):
    repo, scenario = history(tmp_path, 31)
    monkeypatch.setitem(CONFIG, "max_analysis_rows", 30)
    with pytest.raises(SireError) as exc:
        summarize(
            repo, Ledger(store), "test-only", "LUBE-009", scenario["reference_at"]
        )
    assert exc.value.code == "analysis_row_budget"


def test_equipment_role_instead_of_demo_asset_number_controls_rule():
    row = {
        "available": True,
        "delta": 0,
        "recent_mean": 4,
        "evidence_id": "test-only-pressure",
    }
    outputs = []
    for identifier in ["LUBE-501", "LUBE-001", "SKID-42"]:
        outputs.append(
            rank(
                [
                    {
                        "asset_id": identifier,
                        "asset_type": "LUBE",
                        "channels": {"oil_pressure": row},
                    }
                ],
                [],
            )
        )
    assert outputs[0] == outputs[1] == outputs[2]
    assert next(h for h in outputs[0] if h["id"] == "lubrication_loss")[
        "contradictions"
    ] == ["test-only-pressure"]


def test_external_corpus_without_intervention_model_fails_with_typed_error(
    tmp_path, store
):
    repo, _ = history(tmp_path, 31)
    with pytest.raises(SireError) as exc:
        compare(repo, Ledger(store), "test-only", {"service_hour": 24})
    assert (
        exc.value.code == "external_simulation_unsupported" and exc.value.status == 422
    )


def test_closing_after_first_sse_event_always_releases_job_and_conversation(store):
    async def run():
        cid = store.create_conversation("Test-only early stream close")["id"]
        service = ChatService(store)
        generator = service.events(
            cid, "test-only-close", "Hello", [], "chat", None, None, False
        )
        assert (await anext(generator))["type"] == "started"
        await generator.aclose()
        assert not service.jobs and not service.active_conversations
        messages = store.messages(cid)
        assert (
            messages[-1]["role"] == "assistant"
            and messages[-1]["status"] == "cancelled"
        )

    asyncio.run(run())


def test_same_type_request_routes_actual_peer_tool_and_keeps_requested_identity():
    plan = plan_workspace(
        "Compare LUBE-009 against its same-type peers using latest telemetry",
        {"scenario_id": "test-only", "asset_id": "LUBE-009"},
    )
    call = next(call for call in plan.tools if call.tool_id == "fleet.overview")
    assert call.arguments["peer_asset_id"] == "LUBE-009"


def test_peer_filter_uses_registry_type_and_missing_history_is_not_healthy(
    tmp_path, store
):
    repo, scenario = history(tmp_path, 31)
    with sqlite3.connect(repo.path) as db:
        db.execute(
            "INSERT INTO assets VALUES(?,?,?)",
            (
                "test-only",
                "SKID-42",
                json.dumps({"id": "SKID-42", "asset_type": "LUBE"}),
            ),
        )
        db.execute(
            "INSERT INTO assets VALUES(?,?,?)",
            (
                "test-only",
                "MOTOR-009",
                json.dumps({"id": "MOTOR-009", "asset_type": "MOTOR"}),
            ),
        )
    result = overview(
        repo, Ledger(store), "test-only", scenario["reference_at"], "LUBE-009"
    )
    assert {row["asset_id"] for row in result["assets"]} == {"LUBE-009", "SKID-42"}
    assert (
        next(row for row in result["assets"] if row["asset_id"] == "SKID-42")["quality"]
        == "missing_or_insufficient"
    )
    assert result["evidence_ids"] == list(
        dict.fromkeys(e for row in result["assets"] for e in row["evidence_ids"])
    )
