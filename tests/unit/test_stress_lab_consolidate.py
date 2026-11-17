"""Test-only result inventories verify immutable byte-level answer sealing and duplicate refusal."""

import hashlib
import json
import pytest
import scripts.stress_lab.consolidate as module


def test_consolidation_freezes_exact_bytes_and_refuses_duplicate_retries(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/stress_lab_config.yaml").write_text(
        "capability_map: {}\n", encoding="utf-8"
    )
    corpus = tmp_path / "test-only-corpus"
    (corpus / "tests").mkdir(parents=True)
    test = {"test_id": "TEST-ONLY", "expected_tools": [], "expected_assertions": []}
    (corpus / "tests/test_cases.jsonl").write_text(
        json.dumps(test) + "\n", encoding="utf-8"
    )
    (corpus / "schemas").mkdir()
    (corpus / "schemas/evaluation_response_contract.json").write_text(
        json.dumps(
            {
                "type": "object",
                "required": [
                    "test_id",
                    "status",
                    "answer",
                    "tool_calls",
                    "citation_ids",
                    "latency_ms",
                ],
            }
        ),
        encoding="utf-8",
    )
    state = tmp_path / "test-only-state"
    state.mkdir()
    row = {
        "test_id": "TEST-ONLY",
        "priority": "P0",
        "category": "historical_root_cause",
        "executed": False,
        "assessment": "not_run",
        "latency_ms": 0,
        "error_code": "test-only-unrun",
    }
    p = state / "P0_results.jsonl"
    p.write_text(json.dumps(row) + "\n", encoding="utf-8")
    result = module.consolidate(corpus, state)
    seal = json.loads((state / "frozen_answers.json").read_text(encoding="utf-8"))
    assert (
        seal["answers_sha256"]
        == hashlib.sha256((state / "frozen_answers.jsonl").read_bytes()).hexdigest()
    )
    assert result["executed_tests"] == 0 and result["top1_known_cause"] is None
    original_seal = (state / "frozen_answers.json").read_bytes()
    module.consolidate(corpus, state)
    assert (state / "frozen_answers.json").read_bytes() == original_seal
    bad_seal = dict(seal, answers_sha256="not-the-original-digest")
    (state / "frozen_answers.json").write_text(json.dumps(bad_seal), encoding="utf-8")
    with pytest.raises(ValueError, match="seal"):
        module.consolidate(corpus, state)
    (state / "frozen_answers.json").write_bytes(original_seal)
    continuation = tmp_path / "test-only-continuation"
    continuation.mkdir()
    addition = {
        **row,
        "executed": True,
        "assessment": "needs_review",
        "continuation_of_answers_sha256": seal["answers_sha256"],
    }
    (continuation / "completion_results.jsonl").write_text(
        json.dumps(addition) + "\n", encoding="utf-8"
    )
    (continuation / "completion_audit.json").write_text(
        json.dumps(
            {
                "parent_answers_sha256": seal["answers_sha256"],
                "selected_test_ids": [row["test_id"]],
            }
        ),
        encoding="utf-8",
    )
    combined = module.consolidate(corpus, state, completion=continuation)
    assert combined["executed_tests"] == 1
    combined_seal = (state / "assessment_answers.json").read_bytes()
    module.consolidate(corpus, state, completion=continuation)
    assert (state / "assessment_answers.json").read_bytes() == combined_seal
    assert (state / "frozen_answers.json").read_bytes() == original_seal
    combined_hash = json.loads(combined_seal)["answers_sha256"]
    assert (
        combined_hash
        == hashlib.sha256((state / "assessment_answers.jsonl").read_bytes()).hexdigest()
    )
    p.write_text(p.read_text(encoding="utf-8") * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        module.consolidate(corpus, state)


def test_projection_preserves_unrun_and_cancelled_status_without_fake_text():
    row = {
        "test_id": "TEST-ONLY",
        "status": "ok",
        "executed": True,
        "raw_chat": {"status": "cancelled"},
    }
    projected = module.adapter_projection(row)
    assert projected["status"] == "cancelled" and projected["answer"] == ""
    assert row["status"] == "ok"
    blocked = module.adapter_projection(
        {"test_id": "TEST-ONLY", "executed": False, "error_code": "test-only-budget"}
    )
    assert (
        blocked["status"] == "blocked"
        and blocked["tool_calls"] == []
        and blocked["answer"] == ""
    )


def test_completion_retains_unrun_origin_and_refuses_replacing_an_executed_failure():
    original = [
        {"test_id": "a", "executed": False},
        {"test_id": "b", "executed": True, "assessment": "fail"},
    ]
    extra = {"test_id": "a", "executed": True, "continuation_of_answers_sha256": "seal"}
    merged = module.merge_completion(original, [extra], "seal")
    assert merged[0]["original_unrun_record"] == original[0]
    assert merged[1] == original[1] and "original_unrun_record" not in original[0]
    with pytest.raises(ValueError, match="overwrite"):
        module.merge_completion(original, [{**extra, "test_id": "b"}], "seal")
    with pytest.raises(ValueError, match="overwrite"):
        module.merge_completion(original, [extra, extra], "seal")
    with pytest.raises(ValueError, match="parent"):
        module.merge_completion(original, [extra], "another-seal")
