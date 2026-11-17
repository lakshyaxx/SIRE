"""Continuation selection never retries executed failures or interrupts shared services."""

from scripts.stress_lab.completion import completion_cases


def test_completion_selects_only_unexecuted_budget_cases_in_priority_order():
    rows = [
        {
            "test_id": "b",
            "priority": "P1",
            "executed": False,
            "error_code": "bounded_model_budget",
        },
        {
            "test_id": "a",
            "priority": "P0",
            "executed": False,
            "error_code": "bounded_model_budget",
        },
        {
            "test_id": "c",
            "priority": "P0",
            "executed": True,
            "assessment": "fail",
            "error_code": "bounded_model_budget",
        },
        {
            "test_id": "d",
            "priority": "P1",
            "executed": False,
            "error_code": "would_disrupt_shared_ollama",
        },
        {
            "test_id": "e",
            "priority": "P2",
            "executed": False,
            "error_code": "bounded_load",
        },
    ]
    tests = {r["test_id"]: r for r in rows}
    assert [r["test_id"] for r in completion_cases(rows, tests)] == ["a", "b"]
