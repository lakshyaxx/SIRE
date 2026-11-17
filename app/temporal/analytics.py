"""Prefix-only deterministic analytics with exact immutable row snapshots."""

from collections import defaultdict
from statistics import mean
from app.evidence.ledger import Ledger
from app.simulation.repository import Observations
from app.simulation.settings import CONFIG
from app.core.errors import SireError


def summarize(
    repo: Observations, ledger: Ledger, scenario_id: str, asset_id: str, as_of: str
) -> dict:
    """Compare visible prefix baseline/recent samples; never normalize using future data."""
    rows = []
    offset = 0
    while True:
        page = repo.telemetry(scenario_id, asset_id, as_of, limit=5000, offset=offset)
        if len(rows) + len(page) > CONFIG["max_analysis_rows"]:
            raise SireError(
                "analysis_row_budget",
                "The visible history exceeds the configured analysis budget; no incomplete recent-window summary was returned.",
                413,
            )
        rows.extend(page)
        if len(page) < 5000:
            break
        offset += len(page)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["channel"]].append(row)
    channels = {}
    for channel, samples in grouped.items():
        baseline = [
            r for r in samples[:24] if r["quality"] == "good" and r["value"] is not None
        ]
        recent = [
            r for r in samples[-6:] if r["quality"] == "good" and r["value"] is not None
        ]
        valid = [
            r for r in samples if r["quality"] == "good" and r["value"] is not None
        ]
        available = len(baseline) >= 6 and len(recent) >= 4 and len(samples) >= 30
        stats = {
            "baseline_mean": mean(r["value"] for r in baseline) if baseline else None,
            "recent_mean": mean(r["value"] for r in recent) if recent else None,
            "count": len(samples),
            "valid_count": len(valid),
            "missing_count": len(samples) - len(valid),
            "available": available,
        }
        stats["delta"] = (
            stats["recent_mean"] - stats["baseline_mean"] if available else None
        )
        record = ledger.add(
            "sire_synthetic_scenario",
            f"{asset_id}/{channel} observed window",
            {"statistics": stats, "rows": samples},
            {
                "table": "telemetry",
                "scenario_id": scenario_id,
                "asset_id": asset_id,
                "channel": channel,
                "start": samples[0]["observed_at"],
                "end": samples[-1]["observed_at"],
            },
            observed_at=samples[-1]["observed_at"],
            available_at=max(r["available_at"] for r in samples),
            asset_id=asset_id,
            scenario_id=scenario_id,
            unit=samples[0]["unit"],
            quality=(
                "synthetic_good_with_gaps"
                if stats["missing_count"]
                else "synthetic_good"
            ),
            method="prefix_baseline24_recent6_paged_v2",
        )
        channels[channel] = {
            **stats,
            "unit": samples[0]["unit"],
            "evidence_id": record.id,
            "latest_observed_at": samples[-1]["observed_at"],
        }
    return {
        "asset_id": asset_id,
        "asset_type": repo.asset(scenario_id, asset_id).get("asset_type")
        or asset_id.partition("-")[0],
        "as_of": as_of,
        "channels": channels,
        "evidence_ids": [r["evidence_id"] for r in channels.values()],
        "method": "first 24 visible samples vs latest 6; minimum 30 total/6 baseline/4 recent valid samples",
        "limitations": [
            "Trend differences do not prove physical causes.",
            "Baseline uses visible prefix only; no future normalization.",
        ],
    }


def chronology(
    repo: Observations,
    ledger: Ledger,
    scenario_id: str,
    as_of: str,
    asset_ids: list[str],
) -> list[dict]:
    """Create exact cited chronology from only currently available event records."""
    result = []
    for event in repo.events(scenario_id, as_of, asset_ids):
        row = ledger.add(
            "sire_synthetic_scenario",
            "Synthetic facility event",
            event,
            {"table": "events", "row_id": event["id"], "scenario_id": scenario_id},
            observed_at=event["observed_at"],
            available_at=event["available_at"],
            asset_id=event["asset_id"],
            scenario_id=scenario_id,
            method="exact_event_row",
        )
        result.append({**event, "evidence_id": row.id})
    return result
