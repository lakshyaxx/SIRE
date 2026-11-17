"""Clearly test-only scoring contracts; no actual evaluator labels are accessed by pytest."""

import hashlib
import json
import pytest
from scripts.stress_lab.offline_evaluator import evaluate


def test_offline_scoring_requires_frozen_answers_and_external_approved_mapping(
    tmp_path,
):
    answers = tmp_path / "test-only-answers.jsonl"
    answers.write_text(
        json.dumps(
            {
                "incident_id": "TEST-ONLY",
                "category": "historical_root_cause",
                "hypotheses": [{"id": "test-only-engine-id", "status": "supported"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    frozen = tmp_path / "test-only-frozen.json"
    frozen.write_text(
        json.dumps(
            {"answers_sha256": hashlib.sha256(answers.read_bytes()).hexdigest()}
        ),
        encoding="utf-8",
    )
    labels = tmp_path / "test-only-labels.jsonl"
    labels.write_text(
        json.dumps(
            {
                "incident_id": "TEST-ONLY",
                "case_type": "known_cause",
                "cause_codes": ["test-only-code"],
                "split": "development",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    contract = tmp_path / "test-only-contract.json"
    contract.write_text(
        json.dumps(
            {
                "approved_by_evaluator": False,
                "multicause_policy": "any_approved_cause",
                "engine_to_evaluator_cause": {"test-only-engine-id": "test-only-code"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="approval"):
        evaluate(answers, frozen, labels, contract)
    policy = json.loads(contract.read_text(encoding="utf-8"))
    policy["approved_by_evaluator"] = True
    contract.write_text(json.dumps(policy), encoding="utf-8")
    result = evaluate(answers, frozen, labels, contract)
    assert (
        result["aggregate"]["known_causes"] == result["aggregate"]["top1_correct"] == 1
    )
    assert "test-only-code" not in json.dumps(result) and "TEST-ONLY" not in json.dumps(
        result
    )
    answers.write_text(answers.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        evaluate(answers, frozen, labels, contract)
