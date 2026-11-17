"""Explainable differential investigation over observed synthetic facility data, without truth access."""

import asyncio
import time
import uuid
from app.evidence.ledger import Ledger, digest
from app.orchestration.runtime import Invocation, Plan, Runner
from app.simulation.repository import Observations
from app.simulation.settings import CONFIG
from app.temporal.analytics import summarize, chronology
from app.storage.database import now

# Expected consequences are domain rules, not incident labels or fitted model predictions.
RULES = {
    "lubrication_loss": (
        "Lubrication supply deterioration",
        [
            ("LUBE", "oil_pressure", "down"),
            ("*", "vibration", "up"),
            ("*", "bearing_temp", "up"),
            ("*", "discharge_temp", "up"),
        ],
    ),
    "filter_restriction": (
        "Oil-filter restriction as a possible contributor",
        [("LUBE", "filter_dp", "up"), ("LUBE", "oil_pressure", "down")],
    ),
    "misalignment": ("Mechanical alignment problem", [("*", "vibration", "up")]),
    "cavitation": (
        "Process starvation / cavitation",
        [
            ("PUMP", "flow", "down"),
            ("COMP", "suction_pressure", "down"),
            ("PUMP", "vibration", "up"),
        ],
    ),
    "pressure_control": (
        "Pressure-control actuator mismatch",
        [("VALVE", "position_error", "up")],
    ),
    "cooling_degradation": (
        "Cooling supply deterioration",
        [
            ("HEAT", "coolant_flow", "down"),
            ("*", "winding_temp", "up"),
            ("*", "discharge_temp", "up"),
        ],
    ),
    "overload": (
        "Elevated electrical/process load",
        [
            ("MOTOR", "load", "up"),
            ("MOTOR", "current", "up"),
            ("MOTOR", "winding_temp", "up"),
        ],
    ),
    "sensor_fault": ("Temperature sensor disagreement", []),
    "deferred_service": ("Deferred inspection as a contextual contributor", []),
}


def rank(summaries: list[dict], events: list[dict]) -> list[dict]:
    """Score distinct testable mechanisms using transparent independent-channel rules."""
    measurements = {
        (s["asset_id"], c): r for s in summaries for c, r in s["channels"].items()
    }
    thresholds = CONFIG["trend_thresholds"]
    roles = {
        s["asset_id"]: (s.get("asset_type") or s["asset_id"].partition("-")[0]).upper()
        for s in summaries
    }

    def role_measurements(role: str, channel: str) -> list[dict]:
        return [
            row
            for (asset, measured_channel), row in measurements.items()
            if roles[asset] == role and measured_channel == channel
        ]

    def changed(row: dict, channel: str, direction: str) -> bool:
        if row.get("delta") is None:
            return False
        threshold = abs(thresholds.get(channel, 1))
        return (
            row["delta"] > threshold if direction == "up" else row["delta"] < -threshold
        )

    result = []
    for key, (mechanism, expected) in RULES.items():
        support, conflicts, missing = [], [], []
        for asset, channel, direction in expected:
            entries = [
                r
                for (a, c), r in measurements.items()
                if c == channel and (asset == "*" or roles[a] == asset)
            ]
            available = [r for r in entries if r.get("available")]
            if not available:
                missing.append(f"{asset}/{channel}: sufficient valid observations")
            for r in available:
                if changed(r, channel, direction):
                    support.append(r["evidence_id"])
        if key in {"lubrication_loss", "filter_restriction"}:
            for r in role_measurements("LUBE", "oil_pressure"):
                if (
                    r["available"]
                    and abs(r["delta"]) < abs(thresholds["oil_pressure"]) / 2
                ):
                    conflicts.append(r["evidence_id"])
        if key == "misalignment":
            for role, channel, direction in [
                ("LUBE", "oil_pressure", "down"),
                ("MOTOR", "load", "up"),
            ]:
                for r in role_measurements(role, channel):
                    if r["available"] and changed(r, channel, direction):
                        conflicts.append(r["evidence_id"])
        if key == "sensor_fault":
            sensor_support = []
            for asset, role in roles.items():
                if role != "PUMP":
                    continue
                a = measurements.get((asset, "bearing_temp"))
                b = measurements.get((asset, "temperature_backup"))
                v = measurements.get((asset, "vibration"))
                if (
                    a
                    and b
                    and a["available"]
                    and b["available"]
                    and abs(a["recent_mean"] - b["recent_mean"]) > 10
                ):
                    sensor_support.extend([a["evidence_id"], b["evidence_id"]])
                    if v and v["available"] and abs(v["delta"]) < 0.5:
                        sensor_support.append(v["evidence_id"])
            support.extend(sensor_support)
            if not sensor_support:
                missing.append("Independent redundant measurement disagreement")
        if key == "deferred_service":
            support.extend(
                e["evidence_id"]
                for e in events
                if e["event_type"] == "service_deferred"
            )
        support = list(dict.fromkeys(support))
        conflicts = list(dict.fromkeys(conflicts))
        score = 3 * len(support) - 2 * len(conflicts) - 0.25 * len(missing)
        status = (
            "supported"
            if len(support) >= 2 and score >= 4
            else "active" if support else "weakened" if conflicts else "inconclusive"
        )
        result.append(
            {
                "id": key,
                "mechanism": mechanism,
                "status": status,
                "score": score,
                "support": support,
                "contradictions": conflicts,
                "expected_observations": [f"{a}/{c} {d}" for a, c, d in expected],
                "missing_measurements": missing,
                "next_checks": [
                    "Qualified inspection or independent measurement of the proposed mechanism; never operate equipment automatically."
                ],
                "provenance": "sire-facility-rules-2-equipment-roles",
                "support_band": "moderate" if status == "supported" else "low",
                "limitations": "Rule-based consistency ranking, not probability or proof; stable channels only weaken, never absolutely reject.",
            }
        )
    return sorted(result, key=lambda h: (-h["score"], h["id"]))


async def investigate_facility(
    repo: Observations,
    ledger: Ledger,
    scenario_id: str,
    asset_id: str,
    as_of: str | None,
    cancelled: asyncio.Event,
    *,
    parent_case_id: str | None = None,
) -> dict:
    """Expand scope through real graph/temporal tools and stop on repeated/no-new evidence state."""
    cutoff = repo.cutoff(scenario_id, as_of)
    repo.asset(scenario_id, asset_id)
    plan = Plan(
        intent="incident_investigation",
        goals=[
            "Investigate only observations available at cutoff",
            "Compare mechanisms without hidden truth",
        ],
        tools=[
            Invocation(tool_id="temporal.summary"),
            Invocation(tool_id="assets.relations"),
            Invocation(tool_id="hypotheses.rank"),
        ],
        deadline_seconds=CONFIG["deadline_seconds"],
        max_tool_calls=CONFIG["max_tool_calls"],
    )
    runner = Runner(ledger, plan)
    started = time.monotonic()
    summaries = []
    events = []
    history = []
    seen = set()
    hypotheses = []
    scope = [asset_id]
    reason = "max_rounds"
    status = "complete"
    try:
        for iteration in range(CONFIG["max_investigation_rounds"]):
            if cancelled.is_set():
                raise asyncio.CancelledError()
            async with runner.span("temporal.summary") as step:
                existing = {s["asset_id"] for s in summaries}
                for selected in scope:
                    if selected not in existing:
                        summaries.append(
                            await asyncio.to_thread(
                                summarize, repo, ledger, scenario_id, selected, cutoff
                            )
                        )
                step["output_evidence_ids"] = [
                    i for s in summaries for i in s["evidence_ids"]
                ]
            async with runner.span("temporal.events") as step:
                events = await asyncio.to_thread(
                    chronology, repo, ledger, scenario_id, cutoff, scope
                )
                step["output_evidence_ids"] = [e["evidence_id"] for e in events]
            async with runner.span("hypotheses.rank"):
                hypotheses = rank(summaries, events)
            state = digest([hypotheses, sorted(scope)])
            history.append(
                {
                    "round": iteration + 1,
                    "state_sha256": state,
                    "evidence_count": sum(len(s["evidence_ids"]) for s in summaries)
                    + len(events),
                    "hypothesis_ids": [h["id"] for h in hypotheses],
                    "novel": state not in seen,
                }
            )
            if state in seen:
                reason = "repeated_state_no_progress"
                break
            seen.add(state)
            if iteration == 0:
                async with runner.span("assets.relations"):
                    edges = repo.relations(scenario_id, asset_id, cutoff, depth=1)
                    scope = sorted(
                        {
                            asset_id,
                            *[e["source"] for e in edges],
                            *[e["target"] for e in edges],
                        }
                    )
            else:
                reason = "evidence_exhausted"
                break
        evidence_ids = list(
            dict.fromkeys(
                [i for s in summaries for i in s["evidence_ids"]]
                + [e["evidence_id"] for e in events]
            )
        )
        for h in hypotheses:
            assert set(h["support"] + h["contradictions"]).issubset(evidence_ids)
        supported = [h["id"] for h in hypotheses if h["status"] == "supported"]
        inconclusive = not supported
        result = {
            "id": str(uuid.uuid4()),
            "parent_case_id": parent_case_id,
            "scenario_id": scenario_id,
            "asset_id": asset_id,
            "as_of": cutoff,
            "created_at": now(),
            "source_type": "sire_synthetic_scenario",
            "confirmation_status": "simulation_unconfirmed",
            "hypotheses": hypotheses,
            "evidence_ids": evidence_ids,
            "summaries": summaries,
            "timeline": events,
            "rounds": history,
            "stop_reason": reason,
            "conclusion": (
                "Insufficient independent evidence to determine a cause."
                if inconclusive
                else "Several evidence-consistent mechanisms remain; qualified review is needed."
            ),
            "abstained": inconclusive,
            "possible_contributors": supported,
            "run_id": runner.id,
            "elapsed_seconds": time.monotonic() - started,
            "limitations": [
                "Synthetic toy facility, not a validated physical model.",
                "Evidence ordering/graph dependence does not prove causality.",
                "This rule engine does not read evaluator ground truth or use C-MAPSS models.",
                "No automatic actions on real equipment.",
            ],
        }
        if parent_case_id:
            parent = ledger.get("cases", parent_case_id)
            result["revision_source_status"] = (
                "same_evidence_snapshot"
                if set(parent["evidence_ids"]) == set(evidence_ids)
                else "changed_evidence_snapshot_not_proof_of_new_measurements"
            )
        ledger.save("cases", result, result["id"])
        return result
    except asyncio.CancelledError:
        status = "cancelled"
        raise
    except Exception:
        status = "error"
        raise
    finally:
        runner.finish(status)
