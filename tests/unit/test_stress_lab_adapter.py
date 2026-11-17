"""Harness boundary/denominator/source-support regressions; no private evaluator input."""

import sqlite3
import pytest
from scripts.stress_lab.corpus import safe_fixture, audit
from scripts.stress_lab.evaluation import (
    scorecard,
    verify_snapshot,
    capability_coverage,
)
from scripts.stress_lab.runner import Assessment, MemoryProbe


def test_public_fixture_boundary_rejects_evaluator_and_path_escape(tmp_path):
    (tmp_path / "valid.txt").write_text("Test-only public data")
    assert safe_fixture(tmp_path, "valid.txt").name == "valid.txt"
    for name in [
        "../outside.txt",
        "evaluator_only/labels.jsonl",
        "private/answers.json",
    ]:
        with pytest.raises(ValueError):
            safe_fixture(tmp_path, name)
    (tmp_path / "evaluator_only").mkdir()
    with pytest.raises(ValueError, match="isolated"):
        audit(tmp_path)


def test_scorecard_never_counts_unreviewed_claim_as_semantic_pass():
    row = {
        "executed": True,
        "priority": "P0",
        "assessment": "needs_review",
        "latency_ms": 25,
        "citation_checks": [
            {"semantic_status": "needs_human_review", "time_fence": True}
        ],
    }
    result = scorecard([row])
    assert result["citation_semantic_support"]["checked"] == 0
    assert result["citation_semantic_support"]["rate"] is None
    assert result["top1_known_cause"] is None and result["false_positive_rate"] is None


def test_exact_snapshot_support_is_not_an_answer_claim_entailment_pass():
    result = scorecard(
        [
            {
                "executed": True,
                "priority": "P0",
                "assessment": "needs_review",
                "latency_ms": 1,
                "citation_checks": [
                    {
                        "semantic_status": "supported_exact_numeric_claim",
                        "time_fence": True,
                    }
                ],
            }
        ]
    )
    assert result["source_snapshot_support"]["checked"] == 1
    assert result["source_snapshot_support"]["rate"] == 1
    assert result["citation_semantic_support"]["rate"] is None


def test_citation_numeric_support_detects_changed_original_source(tmp_path):
    path = tmp_path / "public-test-only.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE telemetry(asset_id TEXT,timestamp_utc TEXT,pressure REAL)"
        )
        db.execute(
            "INSERT INTO telemetry VALUES(?,?,?)",
            ("TEST-001", "2026-01-01T00:00:00Z", 2.0),
        )
    row = {
        "source_record_id": "telemetry:row:1",
        "source_field": "pressure",
        "asset_id": "TEST-001",
        "observed_at": "2026-01-01T00:00:00+00:00",
        "available_at": "2026-01-01T00:00:00+00:00",
        "quality": "good",
        "value": 7.0,
    }
    record = {
        "evidence": {
            "id": "test-only",
            "available_at": row["available_at"],
            "observation": {
                "rows": [row],
                "statistics": {
                    "baseline_mean": 7.0,
                    "recent_mean": 7.0,
                    "available": False,
                },
            },
        }
    }
    result = verify_snapshot(record, path, row["available_at"])
    assert result["semantic_status"] == "unsupported"


def test_actual_asgi_chat_isolates_harness_conversation(v2client, tmp_path):
    class Corpus:
        """No fixture data needed for this narrow request/trace adapter check."""

        source = tmp_path / "not-used.sqlite3"

    runner = Assessment(v2client, Corpus(), tmp_path / "traces")
    cid = runner.conversation("test-only")
    answer = runner.chat(cid, "Hello", [])
    assert answer["status"] == "complete"
    assert [step["tool_id"] for step in answer["trace"]["steps"]] == [
        "conversation.respond"
    ]
    assert all(call["status"] == 200 for call in runner.calls)


def test_upload_success_is_not_evidence_that_vision_or_retrieval_executed():
    result = {"api_calls": [{"path": "/attachments", "status": 200}], "tool_calls": []}
    mapping = {"vision_analyze": ["vision.inspect"], "ingest_file": ["api.attachments"]}
    coverage = capability_coverage(result, list(mapping), mapping)
    assert not coverage["vision_analyze"]["fulfilled"]
    assert coverage["ingest_file"]["fulfilled"]


def test_memory_sampler_returns_only_measured_rss_or_explicit_absence():
    import time

    probe = MemoryProbe()
    probe.start()
    time.sleep(0.12)
    result = probe.finish()
    assert (
        result["sampled_peak_rss_bytes"] is None or result["sampled_peak_rss_bytes"] > 0
    )
    assert probe.thread is None or not probe.thread.is_alive()
