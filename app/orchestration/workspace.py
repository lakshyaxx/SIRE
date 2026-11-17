"""Capability-based scoped planning and actual tool execution for the chat workspace."""

import asyncio
import re
from collections.abc import AsyncIterator
from typing import Any
import yaml
from pydantic import BaseModel, ConfigDict, Field
from app.core.config import ROOT
from app.core.errors import SireError
from app.orchestration.runtime import Invocation, Plan, Runner

POLICY = yaml.safe_load((ROOT / "config/intelligence.yaml").read_text(encoding="utf-8"))


class InvestigationContext(BaseModel):
    """A user-selected simulated incident/asset and explicit information cutoff."""

    model_config = ConfigDict(extra="forbid")
    scenario_id: str = Field(max_length=100)
    asset_id: str = Field(max_length=100)
    as_of: str | None = Field(default=None, max_length=50)
    case_id: str | None = Field(default=None, max_length=100)


def plan_workspace(
    content: str, context: dict | None, investigate: bool = False
) -> Plan | None:
    """Select available scoped capabilities from user intent, never from uploaded instructions."""
    if not context or re.fullmatch(
        r"\s*(?:hi|hello|hey|thanks|thank you)[!.\s]*", content, re.I
    ):
        return None
    selected = InvestigationContext.model_validate(context)
    text = content.casefold()
    intents = {
        key
        for key, terms in POLICY["intents"].items()
        if any(term in text for term in terms)
    }
    if investigate:
        intents.add("investigation")
    if selected.case_id and re.search(
        r"\b(?:revise|revisit|reconsider|update)\b", text
    ):
        intents.add("investigation")
    if not intents:
        return None
    scope = selected.model_dump(exclude={"case_id"}, exclude_none=True)
    # An explicitly named asset overrides the picker within the same selected incident.
    named = re.findall(
        r"\b(?:PUMP|COMP|VALVE|MOTOR|LUBE|HEAT)-\d{3}\b", content.upper()
    )
    if len(set(named)) == 1:
        scope["asset_id"] = named[0]
        if named[0] != selected.asset_id:
            selected.case_id = None
    calls: list[Invocation] = []
    if intents & {"investigation", "temporal", "onset"}:
        calls.append(Invocation(tool_id="temporal.summary", arguments=scope))
    if intents & {"events", "investigation", "onset"}:
        calls.append(Invocation(tool_id="events.timeline", arguments=scope))
    if intents & {"graph", "investigation"}:
        calls.append(Invocation(tool_id="assets.relations", arguments=scope))
    needs_case = "investigation" in intents or bool(
        intents & {"report", "memory"} and not selected.case_id
    )
    if needs_case:
        arguments = dict(scope)
        if selected.case_id and re.search(
            r"\b(?:revise|revisit|reconsider|update)\b", text
        ):
            arguments["parent_case_id"] = selected.case_id
        calls.append(Invocation(tool_id="facility.investigate", arguments=arguments))
    for intent, tool in [("report", "case.report"), ("memory", "case.similar")]:
        if intent in intents:
            calls.append(
                Invocation(
                    tool_id=tool,
                    arguments={"case_id": selected.case_id},
                    depends_on=["facility.investigate"] if needs_case else [],
                )
            )
    if "fleet" in intents:
        arguments = dict(scope)
        if re.search(r"\b(?:same.type|peers)\b", text):
            arguments["peer_asset_id"] = scope["asset_id"]
        calls.append(Invocation(tool_id="fleet.overview", arguments=arguments))
    if "intervention" in intents:
        changes: dict[str, Any] = {}
        service = re.search(
            r"(?:service|serviced|repair|repaired|maintenance).*?hour\s*(\d{1,2})", text
        )
        load = re.search(r"(?:reduce|lower).*?load.*?(\d{1,2})\s*(?:%|percent)", text)
        if service:
            changes["service_hour"] = int(service.group(1))
        if load:
            changes["load_factor"] = 1 - int(load.group(1)) / 100
        if not changes:
            raise SireError(
                "intervention_parameters",
                "Specify the simulated assumption, for example service at hour 48 or reduce load by 20%.",
            )
        calls.append(
            Invocation(tool_id="simulation.compare", arguments={**scope, **changes})
        )
    return Plan(
        intent="scoped_facility_" + "_".join(sorted(intents)),
        goals=[
            "Answer the requested capabilities from actual time-fenced SIMULATED evidence",
            *sorted(intents),
        ],
        tools=calls,
        deadline_seconds=POLICY["deadline_seconds"],
        max_tool_calls=POLICY["max_tool_calls"],
    )


async def execute_workspace(
    runner: Runner, context: dict, cancelled: asyncio.Event
) -> AsyncIterator[dict]:
    """Run independent cheap reads together, isolate failures, then execute dependent tools."""
    ledger = runner.ledger
    from app.simulation.repository import Observations

    repo = Observations(ledger.store.path.parent / "scenarios")
    scope = InvestigationContext.model_validate(context)
    named_scope = next(
        (
            call.arguments["asset_id"]
            for call in runner.plan.tools
            if "asset_id" in call.arguments
        ),
        scope.asset_id,
    )
    if scope.asset_id != named_scope:
        scope.case_id = None
    scope.asset_id = named_scope
    if scope.asset_id not in {asset["id"] for asset in repo.assets(scope.scenario_id)}:
        raise SireError(
            "asset_missing", "Asset is not present in the selected incident.", 404
        )
    cutoff = repo.cutoff(scope.scenario_id, scope.as_of)
    if scope.case_id:
        saved = ledger.get("cases", scope.case_id)
        if (
            saved["scenario_id"] != scope.scenario_id
            or saved["asset_id"] != scope.asset_id
            or saved["as_of"] != cutoff
        ):
            raise SireError(
                "case_scope_mismatch",
                "The selected case does not match this incident, asset and replay cutoff.",
            )
    result: dict[str, Any] = {
        "requested_capabilities": runner.plan.goals,
        "context": {**scope.model_dump(), "as_of": cutoff},
        "source_type": "sire_synthetic_scenario",
        "outputs": {},
        "errors": [],
        "evidence_ids": [],
    }

    async def invoke(call: Invocation) -> tuple[Invocation, dict | Exception]:
        try:
            return call, await runner.execute(call, cancelled)
        except (SireError, ValueError) as exc:
            return call, exc

    async def collect(calls: list[Invocation], parallel: bool) -> AsyncIterator[dict]:
        for call in calls:
            if cancelled.is_set():
                raise asyncio.CancelledError()
            yield {"type": "tool", "tool": call.tool_id, "status": "running"}
        completed = (
            await asyncio.gather(*(invoke(call) for call in calls))
            if parallel
            else [await invoke(call) for call in calls]
        )
        for call, value in completed:
            if isinstance(value, Exception):
                error = {
                    "tool": call.tool_id,
                    "code": getattr(value, "code", "invalid_tool_input"),
                    "message": getattr(
                        value,
                        "message",
                        "Tool input was invalid; no output substituted.",
                    ),
                }
                result["errors"].append(error)
                yield {"type": "tool", "status": "error", **error}
            else:
                result["outputs"][call.tool_id] = value
                result["evidence_ids"].extend(value.get("evidence_ids", []))
                yield {
                    "type": "tool",
                    "tool": call.tool_id,
                    "status": "complete",
                    "source_ids": value.get("evidence_ids", []),
                }

    reads = [
        call
        for call in runner.plan.tools
        if call.tool_id in POLICY["parallel_read_tools"]
    ]
    async for event in collect(reads, True):
        yield event
    for original in runner.plan.tools:
        if original in reads:
            continue
        call = original.model_copy(deep=True)
        if call.depends_on:
            case = result["outputs"].get("facility.investigate", {}).get("case")
            if not case:
                result["errors"].append(
                    {
                        "tool": call.tool_id,
                        "code": "dependency_failed",
                        "message": "Required case did not complete; dependent tool skipped.",
                    }
                )
                yield {
                    "type": "tool",
                    "tool": call.tool_id,
                    "status": "skipped",
                    "reason": "dependency_failed",
                }
                continue
            call.arguments["case_id"] = case["id"]
        async for event in collect([call], False):
            yield event
    case = result["outputs"].get("facility.investigate", {}).get("case")
    if case:
        result["context"].update(case_id=case["id"], asset_id=case["asset_id"])
    result["evidence_ids"] = sorted(set(result["evidence_ids"]))
    yield {"type": "workspace", "workspace": result}


def render_workspace(result: dict) -> str:
    """Render actual deterministic findings with exact source IDs, avoiding extra model calls."""
    scope = result["context"]
    lines = [
        f"**SIMULATED incident · {scope['asset_id']}**",
        f"Information cutoff: {scope['as_of']}. Incident `{scope['scenario_id']}`.",
    ]
    if "onset" in result.get("requested_capabilities", []):
        lines.append(
            "**Earliest abnormal sample not established.** This tool compares baseline and recent windows and retrieves recorded events; it does not locate or validate the first abnormal sample. A window mean must not be presented as a point measurement at an event time. The source-backed window statistics and chronology below do not establish an exact onset or physical cause."
        )
    for tool, value in result["outputs"].items():
        if tool == "temporal.summary":
            lines.append("### Visible sensor trends")
            for name, channel in value["channels"].items():
                if channel["available"]:
                    lines.append(
                        f"- {name}: baseline {channel['baseline_mean']:.4g}, recent {channel['recent_mean']:.4g} {channel['unit']}; change {channel['delta']:.4g}. [{channel['evidence_id']}]"
                    )
                else:
                    lines.append(
                        f"- {name}: insufficient valid historical samples; {channel['missing_count']} missing/flagged rows. [{channel['evidence_id']}]"
                    )
        elif tool == "events.timeline":
            lines.append("### Available maintenance and event records")
            lines.extend(
                f"- {e['observed_at']} / available {e['available_at']}: {e['text']} [{e['evidence_id']}]"
                for e in value["events"]
            )
            if not value["events"]:
                lines.append(
                    "No event records are available within this scope and cutoff."
                )
        elif tool == "facility.investigate":
            case = value["case"]
            if case.get("parent_case_id"):
                lines.append(
                    f"Revisited saved case `{case['parent_case_id']}`. Source snapshot status: {case.get('revision_source_status', 'not recorded')}. A revision does not imply a newly supplied inspection or measurement."
                )
            lines += ["### Competing mechanisms", case["conclusion"]]
            for h in case["hypotheses"]:
                lines.append(
                    f"- **{h['mechanism']}** — {h['status']}. Support: {', '.join(h['support']) or 'none established'}. Conflicts: {', '.join(h['contradictions']) or 'none established'}. Missing/next checks: {'; '.join(h['missing_measurements'] or h['next_checks'])}."
                )
            lines.append(
                f"Stop: {case['stop_reason']}. Ordering scores are heuristics, not probabilities."
            )
        elif tool == "assets.relations":
            lines.append("### Recorded dependencies")
            lines.extend(
                f"- {edge['source']} → {edge['target']}: {edge['relation'].replace('_', ' ')}."
                for edge in value["relations"]
            )
        elif tool == "case.report":
            identifier = value["report"]["id"]
            lines.append(
                f"Report created from the frozen evidence snapshot: [PDF](/api/v1/reports/{identifier}/download?format=pdf) · [Markdown](/api/v1/reports/{identifier}/download?format=markdown)."
            )
        elif tool == "case.similar":
            lines.append(
                f"Found {len(value['cases'])} prior provisional comparisons. Open Case memory to inspect shared mechanisms and differences; this is not calibrated causal similarity."
            )
        elif tool == "simulation.compare":
            lines.append("### SIMULATED what-if")
            for row in value["comparison"]:
                lines.append(
                    f"- {row['asset_id']}/{row['channel']}: recent mean difference {row['difference']} {row['unit']}."
                )
        elif tool == "fleet.overview":
            if value.get("comparison_scope") == "same_asset_type":
                lines.append(
                    f"Compared {len(value['assets'])} registered {value['asset_type']} assets within the selected historical window. No cross-type average or failure probability was computed."
                )
                for asset in value["assets"]:
                    lines.append(
                        f"- {asset['asset_id']}: {asset['quality']}; {asset['missing_samples']} missing/flagged samples."
                    )
                    for channel, row in asset["channels"].items():
                        if row["available"]:
                            lines.append(
                                f"  - {channel}: baseline {row['baseline_mean']:.4g}, recent {row['recent_mean']:.4g} {row['unit']}; change {row['delta']:.4g}. [{row['evidence_id']}]"
                            )
            lines.append(
                "Fleet data retrieved. Open the sensor inspector for actual quality, missing values and trends; these are not failure probabilities."
            )
    lines.extend(
        f"Tool unavailable: {e['tool']} — {e['message']}" for e in result["errors"]
    )
    lines.append(
        "Synthetic observations and rule interpretations are separate. Correlation/dependency does not establish physical causation. Use qualified inspection and independent measurements."
    )
    return "\n\n".join(lines)
