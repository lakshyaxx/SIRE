"""Freeze actual responses, derive conservative public checks and publish aggregate local findings."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import yaml
from app.core.config import ROOT
from scripts.stress_lab.corpus import safe_fixture
from scripts.stress_lab.evaluation import capability_coverage, scorecard


def adapter_projection(row: dict) -> dict:
    """Normalize actual transport states to the suggested contract without inventing an answer."""
    projected = dict(row)
    states = [turn.get("status") for turn in row.get("turns", [])]
    if not states and row.get("raw_chat"):
        states = [row["raw_chat"].get("status")]
    actual = row.get("status", "blocked")
    if states:
        actual = (
            "error"
            if any(status in {"error", "partial"} for status in states)
            else (
                "cancelled"
                if any(status == "cancelled" for status in states)
                else actual
            )
        )
    projected["actual_transport_status"] = row.get("status")
    projected["actual_chat_statuses"] = states
    projected["status"] = (
        actual
        if actual in {"ok", "rejected", "blocked", "error", "cancelled"}
        else "error"
    )
    projected.setdefault("answer", "")
    projected.setdefault("tool_calls", [])
    projected.setdefault("citation_ids", [])
    projected.setdefault("fixture_ids", [])
    if not row.get("executed"):
        projected["status"] = "blocked"
        projected["unrun_reason"] = row.get("error_code", "Not executed")
    return projected


def merge_completion(
    original: list[dict], additions: list[dict], digest: str
) -> list[dict]:
    """Add first actual executions only; never replace an executed failure with a retry."""
    indexed = {row["test_id"]: row for row in original}
    seen = set()
    for row in additions:
        identifier = row["test_id"]
        prior = indexed.get(identifier)
        if (
            identifier in seen
            or prior is None
            or prior.get("executed")
            or row.get("continuation_of_answers_sha256") != digest
        ):
            raise ValueError(
                "Continuation cannot overwrite an executed case or change its parent"
            )
        indexed[identifier] = {**row, "original_unrun_record": prior}
        seen.add(identifier)
    return [indexed[row["test_id"]] for row in original]


def consolidate(
    corpus: Path,
    state: Path,
    require_complete: bool = True,
    completion: Path | None = None,
) -> dict:
    """Preserve original phase results and derive grades without reading private truth."""
    corpus, state = corpus.resolve(), state.resolve()
    if not state.is_relative_to(ROOT.resolve()):
        raise ValueError("Assessment outputs must stay inside the workspace")
    tests = {
        row["test_id"]: row
        for row in map(
            json.loads,
            safe_fixture(corpus, "tests/test_cases.jsonl")
            .read_text(encoding="utf-8")
            .splitlines(),
        )
    }
    rows = []
    for priority in ["P0", "P1", "P2"]:
        path = state / (priority + "_results.jsonl")
        if path.is_file():
            rows.extend(
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
    if len({row["test_id"] for row in rows}) != len(rows):
        raise ValueError(
            "Duplicate recorded test results; do not silently select a successful retry"
        )
    if require_complete and {r["test_id"] for r in rows} != set(tests):
        raise ValueError(
            "Record every test, including unrun reasons, before answer freeze"
        )
    policy = yaml.safe_load(
        (ROOT / "tests/stress_lab_config.yaml").read_text(encoding="utf-8")
    )
    frozen_body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    raw_path = state / "frozen_answers.jsonl"
    if require_complete:
        frozen_bytes = frozen_body.encode("utf-8")
        seal_path = state / "frozen_answers.json"
        if raw_path.exists() and raw_path.read_bytes() != frozen_bytes:
            raise ValueError(
                "Frozen responses already differ; preserve the prior assessment"
            )
        digest = hashlib.sha256(frozen_bytes).hexdigest()
        if seal_path.exists():
            seal = json.loads(seal_path.read_text(encoding="utf-8"))
            if not raw_path.exists() or seal["answers_sha256"] != digest:
                raise ValueError(
                    "Existing answer seal does not match original responses"
                )
        else:
            if not raw_path.exists():
                raw_path.write_bytes(frozen_bytes)
            seal_path.write_text(
                json.dumps(
                    {
                        "answers_sha256": digest,
                        "rows": len(rows),
                        "created_utc": datetime.now(timezone.utc).isoformat(),
                        "private_labels_read_before_freeze": False,
                        "scope": "Original actual phase rows, not post-hoc grading. No label/answer tuning.",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
    first_pass = scorecard(rows)
    continuation_metadata = None
    if completion is not None:
        completion = completion.resolve()
        if not completion.is_relative_to(ROOT.resolve()) or not require_complete:
            raise ValueError(
                "Use a complete in-workspace continuation with sealed original answers"
            )
        digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        extra = [
            json.loads(line)
            for line in (completion / "completion_results.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        audit = json.loads(
            (completion / "completion_audit.json").read_text(encoding="utf-8")
        )
        if audit["parent_answers_sha256"] != digest or set(
            audit["selected_test_ids"]
        ) != {r["test_id"] for r in extra}:
            raise ValueError("Continuation inventory or parent seal is incomplete")
        rows = merge_completion(rows, extra, digest)
        combined_body = "".join(
            json.dumps(r, ensure_ascii=False) + "\n" for r in rows
        ).encode("utf-8")
        combined_path = state / "assessment_answers.jsonl"
        combined_seal = state / "assessment_answers.json"
        combined_digest = hashlib.sha256(combined_body).hexdigest()
        if combined_path.exists() and combined_path.read_bytes() != combined_body:
            raise ValueError("Preserve the prior sealed combined assessment")
        if combined_seal.exists():
            if (
                not combined_path.exists()
                or json.loads(combined_seal.read_text(encoding="utf-8"))[
                    "answers_sha256"
                ]
                != combined_digest
            ):
                raise ValueError("Combined assessment seal does not match answers")
        else:
            combined_path.write_bytes(combined_body)
            combined_seal.write_text(
                json.dumps(
                    {
                        "answers_sha256": combined_digest,
                        "parent_answers_sha256": digest,
                        "rows": len(rows),
                        "created_utc": datetime.now(timezone.utc).isoformat(),
                        "scope": "First actual executions plus explicit continuation of previously unrun cases; no executed failure replaced. Original unrun rows retained inline and original phase freeze retained.",
                        "private_labels_read_before_freeze": False,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        continuation_metadata = {
            "first_pass_executed": first_pass["executed_tests"],
            "additional_records": len(extra),
            "additional_actual_executions": sum(bool(r.get("executed")) for r in extra),
            "results_path": str(
                (completion / "completion_results.jsonl").relative_to(ROOT)
            ),
            "sealed_answers_path": str(combined_path.relative_to(ROOT)),
            "answers_sha256": combined_digest,
            "original_answers_sha256": digest,
            "executed_failures_replaced": 0,
        }
    derived = []
    for row in rows:
        grade = dict(row)
        grade["original_assessment"] = row["assessment"]
        test = tests[row["test_id"]]
        if (
            row.get("category") == "speech_transcription"
            and any(
                "silence" in fixture.get("path", "")
                for fixture in row.get("fixture_ids", [])
            )
            and row.get("error_code") in {"no_speech_input", "no_speech_recognized"}
        ):
            grade["assessment"] = "pass_safe_silence_rejection"
            grade["grading_correction"] = (
                "Actual no-speech worker error is the expected honest silence outcome. Original adapter compared an incorrect generic no_speech code; original raw failure retained."
            )
        if row.get("executed"):
            grade["capability_coverage"] = capability_coverage(
                row, test["expected_tools"], policy["capability_map"]
            )
            missing = [
                name
                for name, value in grade["capability_coverage"].items()
                if value["fulfilled"] is False
            ]
            grade["unmet_mapped_capabilities"] = missing
            if missing and grade["assessment"] in {
                "pass_automated_only",
                "needs_review",
            }:
                grade["assessment"] = "fail_capability_coverage"
            grade["remaining_assertions_need_review"] = list(
                test["expected_assertions"]
            )
        derived.append(grade)
    result = scorecard(derived)
    if continuation_metadata is not None:
        result["continuation"] = continuation_metadata
    result.update(
        complete_case_inventory=len(rows) == len(tests),
        corpus_case_inventory=len(tests),
        phase_results_paths=[
            str((state / (p + "_results.jsonl")).relative_to(ROOT))
            for p in ["P0", "P1", "P2"]
            if (state / (p + "_results.jsonl")).is_file()
        ],
        raw_results_frozen=require_complete,
        browser_verification="Blocked: supported browser access host unavailable; no navigation/mobile/keyboard interaction pass",
        hardware_verification="Physical microphone/speaker unverified; recorded-file ASR/TTS are separate",
        availability_warning="Corpus has no independent availability clock for all records. Same-time availability assumptions disclosed; closure content fenced at closed_at; lab analysis excluded.",
    )
    result["by_category"] = {
        category: dict(
            Counter(r["assessment"] for r in derived if r["category"] == category)
        )
        for category in dict.fromkeys(r["category"] for r in derived)
    }
    manual_path = state.parent / "manual_citation_review.jsonl"
    if manual_path.is_file():
        manual = [
            json.loads(line)
            for line in manual_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        supported = sum(row["supported"] is True for row in manual)
        result["manual_semantic_sample"] = {
            "supported": supported,
            "reviewed": len(manual),
            "rate": supported / len(manual) if manual else None,
            "scope": "Small purposive agent visual/source review of explicitly selected claims after inference. Not representative, not private-label accuracy and not pooled with numeric-statistic checks.",
            "review_path": str(manual_path.relative_to(ROOT)),
        }
        result["citation_semantic_support"] = {
            "supported": supported,
            "checked": len(manual),
            "rate": supported / len(manual) if manual else None,
            "scope": result["manual_semantic_sample"]["scope"],
            "review_path": str(manual_path.relative_to(ROOT)),
            "population_rate": None,
        }
    result["memory"] = {
        "sampled_case_count": sum(
            bool(r.get("memory", {}).get("sampled_peak_rss_bytes")) for r in rows
        ),
        "largest_sampled_process_rss_bytes": max(
            (r.get("memory", {}).get("sampled_peak_rss_bytes") or 0 for r in rows),
            default=0,
        )
        or None,
        "scope": "Recorded per-case sampler bounds apply; Windows fallback measures harness working set only. P0 had no psutil and is explicitly unmeasured; Ollama/VRAM/whole-system peaks not inferred.",
    }
    (state / "derived_results.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in derived),
        encoding="utf-8",
    )
    projections = [adapter_projection(row) for row in rows]
    try:
        import jsonschema
    except ImportError:
        result["suggested_contract_validation"] = (
            "jsonschema absent; projection provides required fields/statuses, full schema validation unverified"
        )
    else:
        contract = json.loads(
            safe_fixture(corpus, "schemas/evaluation_response_contract.json").read_text(
                encoding="utf-8"
            )
        )
        for row in projections:
            jsonschema.validate(row, contract)
        result["suggested_contract_validation"] = {
            "validated_rows": len(projections),
            "status": "PASS",
        }
    (state / "evaluation_adapter_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in projections),
        encoding="utf-8",
    )
    (state / "scorecard.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    (ROOT / "docs/STRESS_TEST_SCORECARD.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    """Write local aggregates and optional complete frozen responses for separate private evaluation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--intermediate", action="store_true")
    parser.add_argument("--completion", type=Path)
    args = parser.parse_args()
    result = consolidate(
        args.corpus, args.state, not args.intermediate, args.completion
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in {"by_category"}}, indent=2
        )
    )


if __name__ == "__main__":
    main()
