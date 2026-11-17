"""Synthetic repeatability, truth isolation and two-clock replay fences."""

import json
import sqlite3
import pytest
from app.simulation.generator import seed_scenarios, scenario_records, timestamp
from app.simulation.repository import Observations


def test_same_seed_records_match_and_different_seed_changes():
    a, truth = scenario_records(42, 0)
    b, _ = scenario_records(42, 0)
    c, _ = scenario_records(43, 0)
    assert a == b and a != c
    assert "lubrication_loss" not in json.dumps(a)
    assert truth["mechanisms"] == ["lubrication_loss"]
    assert all(t["source_type"] == "sire_synthetic_scenario" for t in a["telemetry"])


@pytest.fixture
def observations(tmp_path):
    seed_scenarios(tmp_path, 42, [0, 7])
    return Observations(tmp_path)


def test_idempotent_seed_and_core_assets(observations, tmp_path):
    one = seed_scenarios(tmp_path, 42)
    two = seed_scenarios(tmp_path, 42)
    assert one == two and len(observations.scenarios()) == 2
    assert len(observations.assets(observations.scenarios()[0]["id"])) == 6


def test_truth_and_attach_physically_denied(observations, tmp_path):
    with pytest.raises(sqlite3.Error):
        observations.query("SELECT * FROM scenario_truth")
    with pytest.raises(sqlite3.Error):
        observations.query(
            "ATTACH DATABASE ? AS truth", (str(tmp_path / "evaluator_truth.sqlite3"),)
        )
    with pytest.raises(sqlite3.Error):
        observations.query("DELETE FROM telemetry")


def test_future_and_late_entered_facts_absent(observations):
    sid = observations.scenarios()[0]["id"]
    for row in observations.events(sid, timestamp(72)):
        assert row["observed_at"] <= timestamp(72) and row["available_at"] <= timestamp(
            72
        )
        assert row["event_type"] != "late_note"
    assert any(
        e["event_type"] == "late_note" for e in observations.events(sid, timestamp(90))
    )
    assert all(
        t["observed_at"] <= timestamp(48)
        for t in observations.telemetry(sid, "COMP-201", timestamp(48))
    )


def test_graph_scope_and_invalid_times(observations):
    sid = observations.scenarios()[0]["id"]
    relations = observations.relations(sid, "COMP-201", timestamp(48))
    assert any(e["source"] == "LUBE-501" for e in relations)
    with pytest.raises(Exception):
        observations.cutoff(sid, "2020-01-01T00:00:00Z")
    with pytest.raises(Exception):
        observations.cutoff(sid, "2026-11-13T00:00:00")
    with pytest.raises(Exception):
        observations.asset(sid, "OTHER-999")


def test_relative_repository_path(tmp_path, monkeypatch):
    from pathlib import Path

    seed_scenarios(tmp_path / "scenarios", 42, [0])
    monkeypatch.chdir(tmp_path)
    assert len(Observations(Path("scenarios")).scenarios()) == 1
