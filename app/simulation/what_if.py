"""Explicit deterministic toy interventions; never a causal model for real uploaded machinery."""

from statistics import mean
from app.core.errors import SireError
from app.evidence.ledger import Ledger, digest
from app.simulation.generator import scenario_records, VERSION
from app.simulation.repository import Observations


def compare(
    repo: Observations,
    ledger: Ledger,
    scenario_id: str,
    changes: dict,
    as_of: str | None = None,
) -> dict:
    """Regenerate with identical noise seed and bounded changed assumptions, then compare values."""
    scenario = repo.scenario(scenario_id)
    if scenario.get("generator_version") != VERSION:
        raise SireError(
            "external_simulation_unsupported",
            "No compatible intervention model is registered for this external synthetic corpus; no built-in demo trajectory was substituted.",
            422,
        )
    if not changes or set(changes) - {"service_hour", "load_factor"}:
        raise SireError(
            "unsupported_intervention",
            "Choose bounded simulated service_hour or load_factor.",
        )
    cutoff = repo.cutoff(scenario_id, as_of)
    index = int(scenario["name"].rsplit(" ", 1)[1]) - 1
    baseline, _ = scenario_records(scenario["seed"], index)
    altered, _ = scenario_records(scenario["seed"], index, changes)
    assets = [scenario["asset_id"]]
    if "load_factor" in changes and "MOTOR-401" not in assets:
        assets.append("MOTOR-401")
    actual = [
        row for asset in assets for row in repo.telemetry(scenario_id, asset, cutoff)
    ]
    expected = [
        r
        for r in baseline["telemetry"]
        if r["asset_id"] in assets
        and r["observed_at"] <= cutoff
        and r["available_at"] <= cutoff
    ]

    def identity(rows: list[dict]) -> list[tuple]:
        return sorted(
            (r["asset_id"], r["channel"], r["observed_at"], r["value"]) for r in rows
        )

    if identity(actual) != identity(expected):
        raise SireError(
            "simulator_version_mismatch",
            "Observed baseline does not match the installed generator; comparison withheld.",
            503,
        )
    channels = sorted({(r["asset_id"], r["channel"]) for r in actual})
    comparisons = []
    for asset, channel in channels:
        before = [
            r
            for r in baseline["telemetry"]
            if r["asset_id"] == asset
            and r["channel"] == channel
            and r["observed_at"] <= cutoff
            and r["available_at"] <= cutoff
        ]
        after = [
            r
            for r in altered["telemetry"]
            if r["asset_id"] == asset
            and r["channel"] == channel
            and r["observed_at"] <= cutoff
            and r["available_at"] <= cutoff
        ]
        b = [r["value"] for r in before[-6:] if r["value"] is not None]
        a = [r["value"] for r in after[-6:] if r["value"] is not None]
        comparisons.append(
            {
                "asset_id": asset,
                "channel": channel,
                "unit": before[0]["unit"],
                "baseline_recent_mean": mean(b) if b else None,
                "intervention_recent_mean": mean(a) if a else None,
                "difference": mean(a) - mean(b) if a and b else None,
                "trajectory": [
                    {
                        "observed_at": x["observed_at"],
                        "baseline": x["value"],
                        "intervention": y["value"],
                    }
                    for x, y in zip(before, after)
                ],
            }
        )
    result = {
        "label": "SIMULATED WHAT-IF",
        "source_type": "sire_synthetic_scenario",
        "baseline_scenario_id": scenario_id,
        "intervention_scenario_id": altered["scenario"]["id"],
        "as_of": cutoff,
        "seed": scenario["seed"],
        "generator_version": scenario["generator_version"],
        "changes": changes,
        "compared_assets": assets,
        "comparison": comparisons,
        "baseline_sha256": digest(actual),
        "intervention_sha256": digest(
            [
                r
                for r in altered["telemetry"]
                if r["observed_at"] <= cutoff and r["available_at"] <= cutoff
            ]
        ),
        "limitations": [
            "Same initial seed/noise, explicit toy response rules; no physical causal validity claimed.",
            "Service reduces modeled oil-pressure loss over eight hours; it does not guarantee actual prevention.",
            "Load factor changes only the toy motor load/current channels; unrelated asset channels may remain unchanged.",
            "NASA predictors and real uploaded histories are not used.",
        ],
    }
    record = ledger.add(
        "sire_synthetic_scenario",
        "Synthetic what-if comparison",
        result,
        {"scenario_id": scenario_id, "intervention_id": altered["scenario"]["id"]},
        method="same_seed_regeneration_v1",
    )
    return {**result, "evidence_ids": [record.id]}
