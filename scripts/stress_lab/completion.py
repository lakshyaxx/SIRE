"""Run previously unexecuted P0/P1 cases serially in an independent disposable namespace."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import yaml
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.core.config import ROOT
from app.prediction.hub import verify_integrity
from scripts.stress_lab.corpus import PublicCorpus, audit, safe_fixture
from scripts.stress_lab.evaluation import save_scorecard
from scripts.stress_lab.runner import Assessment


def completion_cases(original: list[dict], tests: dict[str, dict]) -> list[dict]:
    """Select only unexecuted budget-limited cases, never successful retries or live outages."""
    selected = []
    for row in original:
        if (
            not row.get("executed")
            and row["priority"] in {"P0", "P1"}
            and row.get("error_code") == "bounded_model_budget"
        ):
            selected.append(tests[row["test_id"]])
    return sorted(selected, key=lambda test: (test["priority"], test["test_id"]))


def main() -> None:
    """Audit public inputs, validate the prior seal and retain each actual new response."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    parent, state = args.parent.resolve(), args.state.resolve()
    allowed = (ROOT / ".runtime/stress_lab").resolve()
    if (
        not parent.is_relative_to(allowed)
        or not state.is_relative_to(allowed)
        or parent == state
    ):
        raise SystemExit("Use separate disposable stress namespaces")
    body = (parent / "frozen_answers.jsonl").read_bytes()
    seal = json.loads((parent / "frozen_answers.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(body).hexdigest()
    if digest != seal["answers_sha256"]:
        raise SystemExit("Original frozen responses do not match their seal")
    original = [json.loads(line) for line in body.decode("utf-8").splitlines()]
    tests = {
        row["test_id"]: row
        for row in map(
            json.loads,
            safe_fixture(args.corpus, "tests/test_cases.jsonl")
            .read_text(encoding="utf-8")
            .splitlines(),
        )
    }
    chosen = completion_cases(original, tests)
    state.mkdir(parents=True, exist_ok=True)
    results = state / "completion_results.jsonl"
    if results.exists() and not args.resume:
        raise SystemExit("Preserve results; use a new namespace or --resume")
    existing = (
        [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines()]
        if results.is_file()
        else []
    )
    seen = {r["test_id"] for r in existing}
    if len(seen) != len(existing) or not seen <= {t["test_id"] for t in chosen}:
        raise SystemExit("Unexpected or duplicate continuation results")
    audit_path = state / "completion_audit.json"
    if not audit_path.exists():
        report = audit(args.corpus)
        report.update(
            parent_answers_sha256=digest,
            selected_test_ids=[t["test_id"] for t in chosen],
            concurrency=1,
            native_integrity_files=verify_integrity(),
            time_utc=datetime.now(timezone.utc).isoformat(),
            source_sha256={
                p.relative_to(ROOT)
                .as_posix(): hashlib.sha256(p.read_bytes())
                .hexdigest()
                for folder in ["app", "config", "scripts/stress_lab"]
                for p in (ROOT / folder).rglob("*")
                if p.is_file() and p.suffix in {".py", ".yaml"}
            },
        )
        audit_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    elif (
        json.loads(audit_path.read_text(encoding="utf-8"))["parent_answers_sha256"]
        != digest
    ):
        raise SystemExit("Continuation parent changed")
    policy = yaml.safe_load(
        (ROOT / "tests/stress_lab_config.yaml").read_text(encoding="utf-8")
    )
    corpus = PublicCorpus(args.corpus, state, policy)
    with TestClient(
        create_app(state_dir=state, probe_model=False), raise_server_exceptions=False
    ) as client:
        runner = Assessment(client, corpus, state / "traces")
        for test in chosen:
            if test["test_id"] in seen:
                continue
            result = runner.run_case(test)
            result["continuation_of_answers_sha256"] = digest
            with results.open("a", encoding="utf-8") as output:
                output.write(json.dumps(result, ensure_ascii=False) + "\n")
            save_scorecard(results)
            print(
                test["test_id"],
                result["assessment"],
                round(result["latency_ms"] / 1000, 3),
                flush=True,
            )


if __name__ == "__main__":
    main()
