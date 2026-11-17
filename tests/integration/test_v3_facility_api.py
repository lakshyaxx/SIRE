"""Real SQLite-backed workflow contracts and historical replay leakage regression."""

from app.simulation.generator import seed_scenarios, timestamp


def test_real_facility_case_and_evidence_resolution(v2client):
    seed_scenarios(v2client.app.state.store.path.parent / "scenarios", 42, [0, 7])
    scenarios = v2client.get("/api/v1/scenarios").json()["scenarios"]
    scenario = next(s for s in scenarios if s["name"].endswith("01"))
    assert "mechanisms" not in str(scenarios)
    sid = scenario["id"]
    cutoff = timestamp(72)
    r = v2client.get(
        f'/api/v1/assets/COMP-201/telemetry?scenario_id={sid}&as_of={cutoff.replace("+","%2B")}&limit=5000'
    )
    assert r.status_code == 200, r.text
    assert all(
        row["observed_at"] <= cutoff and row["available_at"] <= cutoff
        for row in r.json()["records"]
    )
    case = v2client.post(
        "/api/v1/facility/investigations",
        json={"scenario_id": sid, "asset_id": "COMP-201", "as_of": cutoff},
    )
    assert case.status_code == 200, case.text
    result = case.json()
    assert result["evidence_ids"] and len(result["hypotheses"]) >= 2
    for identifier in result["evidence_ids"]:
        evidence = v2client.get("/api/v1/evidence/" + identifier).json()["evidence"]
        assert evidence["available_at"] <= cutoff
    memory = v2client.get("/api/v1/cases").json()["cases"]
    assert memory[0]["id"] == result["id"]
    assert (
        v2client.get("/api/v1/runs/" + result["run_id"] + "/trace").json()["status"]
        == "complete"
    )
