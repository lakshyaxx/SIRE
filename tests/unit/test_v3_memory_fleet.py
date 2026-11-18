"""Fleet quality and case-memory trust/availability filters over actual synthetic records."""

import asyncio
from app.assets.fleet import overview
from app.evidence.ledger import Ledger
from app.investigation.facility import investigate_facility
from app.knowledge.case_memory import _comparison_details, similar_cases
from app.orchestration.workspace import _render_similar_cases
from app.simulation.generator import seed_scenarios, timestamp
from app.simulation.repository import Observations


def test_fleet_data_and_memory_time_isolation(store, tmp_path):
    seed_scenarios(tmp_path / "scenarios", 42, [0])
    repo = Observations(tmp_path / "scenarios")
    s = repo.scenarios()[0]
    ledger = Ledger(store)
    one = asyncio.run(
        investigate_facility(
            repo, ledger, s["id"], s["asset_id"], timestamp(72), asyncio.Event()
        )
    )
    two = asyncio.run(
        investigate_facility(
            repo,
            ledger,
            s["id"],
            s["asset_id"],
            timestamp(96),
            asyncio.Event(),
            parent_case_id=one["id"],
        )
    )
    assert similar_cases(ledger, two["id"])[0]["case_id"] == one["id"]
    assert similar_cases(ledger, two["id"], timestamp(72)) == []
    result = overview(repo, ledger, s["id"], timestamp(48))
    assert len(result["assets"]) == 6
    assert all(
        a["latest_observed_at"] <= timestamp(48) and "failure_probability" not in a
        for a in result["assets"]
    )
    assert ledger.get("cases", two["id"])["parent_case_id"] == one["id"]


def test_prior_case_text_includes_identity_contrasts_strength_and_sources():
    lines = _render_similar_cases(
        [
            {
                "case_id": "CASE-LOCAL-1",
                "asset_id": "PUMP-008",
                "confirmation_status": "provisional",
                "overlap_score": 0.5,
                "shared_mechanisms": ["lubrication deficiency"],
                "different_mechanisms": ["shaft misalignment"],
                "evidence_ids": ["EV:" + "a" * 64],
                "evidence_strength": "provisional_only",
                "overlapping_symptoms": [
                    {"channel": "vibration", "direction": "increasing"}
                ],
                "differing_readings": [
                    {
                        "channel": "vibration",
                        "selected_value": 4.2,
                        "prior_value": 3.1,
                        "unit": "mm/s",
                    }
                ],
                "retrieval_reason": "Shared one provisional mechanism.",
                "asset_context": {
                    "selected": {
                        "asset_id": "PUMP-001",
                        "as_of": "2026-01-02T00:00:00Z",
                    },
                    "prior": {
                        "asset_id": "PUMP-008",
                        "as_of": "2026-01-01T00:00:00Z",
                    },
                },
            }
        ]
    )
    text = "\n".join(lines)
    assert "CASE-LOCAL-1" in text and "PUMP-008" in text
    assert "overlap 0.500" in text and "lubrication deficiency" in text
    assert "shaft misalignment" in text and "[EV:" in text
    assert "vibration increasing" in text and "selected 4.2 vs prior 3.1 mm/s" in text
    assert "Why retrieved" in text and "provisional_only" in text
    assert "Selected PUMP-001" in text and "prior PUMP-008" in text
    assert "not calibrated causal similarity" in text


def test_prior_case_text_is_explicit_when_no_time_eligible_case_exists():
    assert _render_similar_cases([]) == [
        "No earlier time-eligible case comparison was found for this saved case."
    ]


def test_case_comparison_keeps_asset_context_and_unit_safe_reading_differences():
    def saved_case(asset: str, recent: float, delta: float, unit: str) -> dict:
        return {
            "scenario_id": f"SCENARIO-{asset}",
            "asset_id": asset,
            "as_of": "2026-01-01T00:00:00+00:00",
            "summaries": [
                {
                    "asset_id": asset,
                    "channels": {
                        "vibration": {
                            "available": True,
                            "recent_mean": recent,
                            "delta": delta,
                            "unit": unit,
                            "evidence_id": "EV:" + "b" * 64,
                        }
                    },
                }
            ],
        }

    details = _comparison_details(
        saved_case("PUMP-001", 4.2, 1.1, "mm/s"),
        saved_case("PUMP-008", 3.1, 0.4, "mm/s"),
    )
    assert details["asset_context"]["selected"]["asset_id"] == "PUMP-001"
    assert details["asset_context"]["prior"]["asset_id"] == "PUMP-008"
    assert details["overlapping_symptoms"] == [
        {"channel": "vibration", "direction": "increasing"}
    ]
    assert details["differing_readings"][0]["unit"] == "mm/s"
