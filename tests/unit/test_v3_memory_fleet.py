"""Fleet quality and case-memory trust/availability filters over actual synthetic records."""

import asyncio
from app.assets.fleet import overview
from app.evidence.ledger import Ledger
from app.investigation.facility import investigate_facility
from app.knowledge.case_memory import similar_cases
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
