"""Actual scoped planning/execution, persistence and independent-tool failure isolation."""

import asyncio
import json
import pytest
from app.orchestration.workspace import (
    plan_workspace,
    execute_workspace,
    render_workspace,
)
from app.orchestration.runtime import Runner
from app.orchestration.tools import build_registry
from app.evidence.ledger import Ledger
from app.core.errors import SireError
from app.simulation.generator import seed_scenarios, timestamp
from app.simulation.repository import Observations


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Show the vibration trend before this cutoff", {"temporal.summary"}),
        ("Which maintenance records are available?", {"events.timeline"}),
        ("What equipment is upstream?", {"assets.relations"}),
        (
            "Investigate the warning and export a PDF report",
            {
                "temporal.summary",
                "events.timeline",
                "assets.relations",
                "facility.investigate",
                "case.report",
            },
        ),
        ("Find a similar prior case", {"facility.investigate", "case.similar"}),
        ("What if we reduce load by 20%?", {"simulation.compare"}),
    ],
)
def test_request_selects_capabilities(question, expected):
    context = {
        "scenario_id": "test-only-scope",
        "asset_id": "COMP-201",
        "as_of": timestamp(72),
    }
    plan = plan_workspace(question, context)
    assert {call.tool_id for call in plan.tools} == expected
    assert not any(call.tool_id == "llm.chat" for call in plan.tools)


def test_no_implicit_facility_scope_or_greeting_tools():
    assert plan_workspace("Investigate this pump", None) is None
    assert (
        plan_workspace("Hello!", {"scenario_id": "test", "asset_id": "COMP-201"})
        is None
    )
    with pytest.raises(SireError, match="Specify"):
        plan_workspace(
            "What if we intervene?", {"scenario_id": "test", "asset_id": "COMP-201"}
        )


def test_actual_workspace_export_and_failure_isolation(store, tmp_path):
    seed_scenarios(store.path.parent / "scenarios", 42, [0])
    scenario = Observations(store.path.parent / "scenarios").scenarios()[0]
    context = {
        "scenario_id": scenario["id"],
        "asset_id": scenario["asset_id"],
        "as_of": timestamp(72),
    }

    async def run():
        ledger = Ledger(store)
        plan = plan_workspace(
            "Investigate vibration and maintenance, export a PDF", context
        )
        registry = build_registry(store)
        # Test-only fault injection: all remaining tools execute their actual SQLite/report code.
        spec, schema, _ = registry.tools["assets.relations"]

        async def unavailable(args):
            raise SireError(
                "test_only_graph_outage", "Test-only unavailable graph adapter", 503
            )

        registry.tools["assets.relations"] = spec, schema, unavailable
        runner = Runner(ledger, plan, registry)
        events = [
            event async for event in execute_workspace(runner, context, asyncio.Event())
        ]
        result = events[-1]["workspace"]
        assert result["outputs"]["case.report"]["report"]["id"]
        assert result["errors"][0]["code"] == "test_only_graph_outage"
        assert all(
            ledger.resolve(identifier)["evidence"]["available_at"] <= timestamp(72)
            for identifier in result["evidence_ids"]
        )
        assert "SIMULATED" in render_workspace(
            result
        ) and "Tool unavailable" in render_workspace(result)
        statuses = {step["tool_id"]: step["status"] for step in runner.trace["steps"]}
        assert (
            statuses["assets.relations"] == "error" and statuses["case.report"] == "ok"
        )

    asyncio.run(run())


def test_scoped_chat_runs_real_tools_without_provider(v2client):
    store = v2client.app.state.store
    seed_scenarios(store.path.parent / "scenarios", 42, [0])
    scenario = Observations(store.path.parent / "scenarios").scenarios()[0]
    cid = v2client.post("/api/v1/conversations", json={}).json()["id"]
    context = {
        "scenario_id": scenario["id"],
        "asset_id": scenario["asset_id"],
        "as_of": timestamp(72),
    }
    response = v2client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": cid,
            "content": "Investigate this fault and export a report",
            "context": context,
        },
    )
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert events[-1]["status"] == "complete", events
    assert events[-1]["metadata"]["provider"] == "deterministic_tools"
    assert "model" not in events[-1]["metadata"]
    assert events[-1]["metadata"]["model_activity"] == []
    workspace = events[-1]["metadata"]["workspace"]
    assert (
        workspace["outputs"]["facility.investigate"]["case"]["asset_id"]
        == context["asset_id"]
    )
    assert workspace["outputs"]["case.report"]["report"]["id"]
    saved = v2client.get(f"/api/v1/conversations/{cid}").json()["messages"]
    assert {key: saved[0]["metadata"]["context"][key] for key in context} == context
    run_id = saved[-1]["metadata"]["orchestration"]["run_id"]
    trace = v2client.get(f"/api/v1/runs/{run_id}/trace").json()
    assert trace["status"] == "complete"
    assert "llm.chat" not in [step["tool_id"] for step in trace["steps"]]
