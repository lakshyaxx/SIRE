"""Serial actual-API stress tests with raw answers, real traces and explicit incomplete assertions."""

import argparse
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time
import threading
import os
from typing import Any
import yaml
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core.config import ROOT
from app.prediction.hub import catalog, verify_integrity
from scripts.stress_lab.corpus import PublicCorpus, audit, safe_fixture
from scripts.stress_lab.evaluation import (
    verify_snapshot,
    save_scorecard,
    capability_coverage,
)


class MemoryProbe:
    """Sample the harness and child workers; the external Ollama process/VRAM is excluded."""

    def __init__(self) -> None:
        self.stop = threading.Event()
        self.peak = None
        self.thread = None
        self.reason = "External Ollama process/VRAM not included."
        self.scope = (
            "ASGI harness and child workers, 100ms sampling; not whole-system peak"
        )

    def start(self) -> None:
        """Sample optional psutil RSS without installing or changing dependencies."""
        try:
            import psutil

            process = psutil.Process()

            def measure() -> int:
                return sum(
                    p.memory_info().rss
                    for p in [process, *process.children(recursive=True)]
                    if p.is_running()
                )

        except ImportError:
            if os.name != "nt":
                self.reason = "psutil absent on this platform; peak RSS not measured."
                return
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                ] + [
                    (name, ctypes.c_size_t)
                    for name in [
                        "PeakWorkingSetSize",
                        "WorkingSetSize",
                        "QuotaPeakPagedPoolUsage",
                        "QuotaPagedPoolUsage",
                        "QuotaPeakNonPagedPoolUsage",
                        "QuotaNonPagedPoolUsage",
                        "PagefileUsage",
                        "PeakPagefileUsage",
                    ]
                ]

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            handle = kernel.GetCurrentProcess()
            api = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
            api.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
            api.restype = wintypes.BOOL

            def measure() -> int:
                values = Counters()
                values.cb = ctypes.sizeof(values)
                if not api(handle, ctypes.byref(values), values.cb):
                    raise OSError("Current-process memory query failed")
                return int(values.WorkingSetSize)

            self.scope = "Windows current ASGI harness working set only, 100ms sampling"
            self.reason = "psutil absent; native current-process API used. Child workers, external Ollama and VRAM excluded."

        def sample() -> None:
            while not self.stop.is_set():
                try:
                    value = measure()
                    self.peak = max(self.peak or 0, value)
                except Exception as exc:
                    self.reason = (
                        "Memory sample unavailable: "
                        + type(exc).__name__
                        + "; no estimated memory value substituted."
                    )
                self.stop.wait(0.1)

        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()

    def finish(self) -> dict:
        """Stop/join and return actual sampled memory with its measurement boundary."""
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=2)
        return {
            "sampled_peak_rss_bytes": self.peak,
            "scope": self.scope,
            "limitation": self.reason,
        }


class Assessment:
    """Exercise the same API contracts as the frontend, with a fresh disposable store."""

    def __init__(self, client: TestClient, corpus: PublicCorpus, output: Path) -> None:
        self.client, self.corpus, self.output = client, corpus, output
        self.calls: list[dict] = []
        self.evidence_cache: OrderedDict[str, dict] = OrderedDict()
        self.models = catalog()
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / "evidence").mkdir(exist_ok=True)

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Record actual API response status/timing; never invent a specialist invocation."""
        started = time.monotonic()
        response = self.client.request(method, "/api/v1" + path, **kwargs)
        self.calls.append(
            {
                "method": method,
                "path": path,
                "status": response.status_code,
                "elapsed_seconds": time.monotonic() - started,
            }
        )
        return response

    def conversation(self, test_id: str) -> str:
        """Allocate a clean conversation so unrelated cases cannot supply prior evidence."""
        return self.request(
            "POST", "/conversations", json={"title": "Stress Lab " + test_id}
        ).json()["id"]

    def chat(
        self,
        cid: str,
        prompt: str,
        selected: list[str],
        context: dict | None = None,
        **kwargs: Any,
    ) -> dict:
        """Submit real SSE request, preserve deltas and fetch its actual saved trace."""
        response = self.request(
            "POST",
            "/chat/message",
            json={
                "conversation_id": cid,
                "content": prompt,
                "attachment_ids": selected,
                "context": context,
                **kwargs,
            },
        )
        if response.status_code != 200:
            return {
                "http_status": response.status_code,
                "response": response.json(),
                "status": "error",
            }
        events = [
            json.loads(line[6:])
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        last = events[-1] if events else {}
        metadata = last.get("metadata", {})
        result = {
            "events": events,
            "status": last.get("status", "error"),
            "metadata": metadata,
            "answer": "".join(e.get("text", "") for e in events if e["type"] == "delta")
            or next(
                (e.get("content", "") for e in events if e["type"] == "report"), ""
            ),
        }
        run_id = metadata.get("orchestration", {}).get("run_id")
        if run_id:
            result["trace"] = self.request("GET", f"/runs/{run_id}/trace").json()
        result["errors"] = [event for event in events if event["type"] == "error"]
        return result

    def citations(self, identifiers: list[str], cutoff: str | None) -> list[dict]:
        """Resolve sources and verify limited actual support against raw corpus records."""
        checks = []
        for identifier in dict.fromkeys(identifiers):
            if identifier not in self.evidence_cache:
                response = self.request("GET", "/evidence/" + identifier)
                if response.status_code != 200:
                    checks.append(
                        {
                            "evidence_id": identifier,
                            "exists": False,
                            "time_fence": False,
                            "semantic_status": "unsupported",
                            "error_status": response.status_code,
                        }
                    )
                    continue
                record = response.json()
                self.evidence_cache[identifier] = record
                name = hashlib.sha256(identifier.encode()).hexdigest() + ".json"
                (self.output / "evidence" / name).write_text(
                    json.dumps(record, ensure_ascii=False), encoding="utf-8"
                )
            record = self.evidence_cache[identifier]
            self.evidence_cache.move_to_end(identifier)
            while len(self.evidence_cache) > self.corpus.policy["max_cached_evidence"]:
                self.evidence_cache.popitem(last=False)
            check = verify_snapshot(record, self.corpus.source, cutoff)
            check["snapshot_path"] = str(
                (
                    self.output
                    / "evidence"
                    / (hashlib.sha256(identifier.encode()).hexdigest() + ".json")
                ).relative_to(ROOT)
            )
            checks.append(check)
        return checks

    def run_case(self, test: dict) -> dict:
        """Map a declared fixture task onto actual contracts and record every unmet assertion."""
        started = time.monotonic()
        memory = MemoryProbe()
        memory.start()
        self.calls = []
        cid = self.conversation(test["test_id"])
        category, scope = test["category"], None
        result: dict[str, Any] = {
            "test_id": test["test_id"],
            "priority": test["priority"],
            "category": category,
            "incident_id": test.get("incident_id"),
            "asset_id": test.get("asset_id"),
            "split": test["split"],
            "executed": True,
            "status": "ok",
            "assessment": "needs_review",
            "answer": "",
            "conversation_id": cid,
            "fixture_ids": [],
            "tool_calls": [],
            "citation_ids": [],
            "citation_checks": [],
            "checks": {},
            "human_verification_needed": True,
            "expected_assertions": test["expected_assertions"],
            "must_not": test["must_not"],
            "adapter_scope": "Actual SIRE 3.2 ASGI routes; engineering fixture mode is not silently mapped to forced Investigate. Natural wording selects tools. No evaluator labels supplied.",
        }
        try:
            if test.get("incident_id") or test.get("asset_id"):
                scope = self.corpus.ensure_scope(
                    test.get("incident_id"), test.get("asset_id")
                )
                self.request("GET", "/scenarios/" + scope["scenario_id"])
                if category == "temporal_leakage":
                    scope["as_of"] = (
                        datetime.fromisoformat(scope["as_of"]) - timedelta(hours=12)
                    ).isoformat()
            if category == "nasa_model_contract":
                self._native(test, result)
            elif category == "robustness":
                from scripts.stress_lab.reliability import run_reliability

                run_reliability(self, test, result, cid)
            elif category == "load_test":
                from scripts.stress_lab.reliability import run_load

                run_load(self, test, result)
            elif category == "multiturn_context":
                from scripts.stress_lab.reliability import run_multiturn

                run_multiturn(self, test, result, cid, scope)
            else:
                selected = []
                uploads = []
                for relative in test["attachments"]:
                    path = safe_fixture(self.corpus.root, relative)
                    content = path.read_bytes()
                    result["fixture_ids"].append(
                        {
                            "path": relative,
                            "sha256": hashlib.sha256(content).hexdigest(),
                            "bytes": len(content),
                            "synthetic_kind": (
                                "generated_photo"
                                if "generated" in path.name
                                else (
                                    "schematic"
                                    if "schematic" in path.name
                                    else "synthetic_test_fixture"
                                )
                            ),
                        }
                    )
                    response = self.request(
                        "POST",
                        "/attachments",
                        data={"conversation_id": cid},
                        files={
                            "file": (path.name, content, "application/octet-stream")
                        },
                    )
                    uploads.append(
                        {
                            "fixture": relative,
                            "http_status": response.status_code,
                            "response": response.json(),
                        }
                    )
                    if response.status_code != 200:
                        result.update(
                            status="rejected",
                            answer=json.dumps(response.json()),
                            error_code=response.json().get("error", {}).get("code"),
                        )
                        break
                    item = response.json()
                    if item["metadata"].get("media_error"):
                        result.update(
                            status="rejected",
                            answer=json.dumps(item["metadata"]["media_error"]),
                            error_code=item["metadata"]["media_error"]["code"],
                        )
                        break
                    selected.append(item["id"])
                result["uploads"] = uploads
                if category == "invalid_input":
                    result["assessment"] = (
                        "pass" if result["status"] == "rejected" else "needs_review"
                    )
                    result["checks"]["parser_rejected"] = result["status"] == "rejected"
                    result["checks"]["no_unhandled_exception"] = all(
                        u["http_status"] < 500 for u in uploads
                    )
                    if selected:
                        result["answer"] = (
                            "Actual parser accepted this as "
                            + uploads[-1]["response"]["kind"]
                            + "; this does not prove industrial schema validity."
                        )
                elif result["status"] == "rejected":
                    result["assessment"] = (
                        "pass"
                        if category == "speech_transcription"
                        and result.get("error_code")
                        in {"no_speech_input", "no_speech_recognized"}
                        else "fail"
                    )
                else:
                    prompt = test["prompt"]
                    if any(
                        item["synthetic_kind"] in {"generated_photo", "schematic"}
                        for item in result["fixture_ids"]
                    ):
                        kinds = sorted(
                            {item["synthetic_kind"] for item in result["fixture_ids"]}
                        )
                        prompt += (
                            "\nTest-operator metadata from the public corpus README: 100% SYNTHETIC. Visual fixture kind: "
                            + ", ".join(kinds)
                            + ". These are not authenticated photographs of a real failed asset."
                        )
                    if category == "speech_transcription" and uploads:
                        transcript = uploads[-1]["response"]["metadata"].get(
                            "transcript", {}
                        )
                        result["transcript"] = transcript
                        prompt = transcript.get("text", "")
                    answer = self.chat(cid, prompt, selected, scope)
                    result["raw_chat"] = answer
                    result["submitted_prompt"] = prompt
                    result["answer"] = answer.get("answer", "")
                    result["status"] = (
                        "ok" if answer["status"] == "complete" else answer["status"]
                    )
                    trace = answer.get("trace", {})
                    result["tool_calls"] = [
                        step["tool_id"] for step in trace.get("steps", [])
                    ]
                    result["model_identifiers"] = [
                        step["model_provenance"]
                        for step in trace.get("steps", [])
                        if step.get("model_provenance")
                    ]
                    meta = answer.get("metadata", {})
                    result["hypotheses"] = (
                        meta.get("workspace", {})
                        .get("outputs", {})
                        .get("facility.investigate", {})
                        .get("case", {})
                        .get(
                            "hypotheses",
                            meta.get("investigation", {}).get("hypotheses", []),
                        )
                    )
                    result["citation_ids"] = list(
                        dict.fromkeys(
                            meta.get("workspace", {}).get("evidence_ids", [])
                            + [e["id"] for e in meta.get("evidence", [])]
                        )
                    )
                    result["citation_checks"] = self.citations(
                        result["citation_ids"], scope["as_of"] if scope else None
                    )
                    result["checks"].update(
                        response_complete=answer["status"] == "complete",
                        evidence_ids_resolve=all(
                            c["exists"] for c in result["citation_checks"]
                        ),
                        no_future_evidence=all(
                            c["time_fence"] for c in result["citation_checks"]
                        ),
                        timestamps_present=bool(scope and scope.get("as_of")),
                        references_incident=not test.get("incident_id")
                        or test["incident_id"] in result["answer"],
                        multiple_hypotheses=len(result["hypotheses"]) >= 2,
                    )
                    result["checks"]["latest_visible_samples_included"] = all(
                        c.get("latest_visible_sample_included", True)
                        for c in result["citation_checks"]
                    )
                    if category == "historical_root_cause":
                        result["assessment"] = (
                            "pass_automated_only"
                            if all(result["checks"].values())
                            else "fail"
                        )
                    elif category == "temporal_leakage":
                        result["assessment"] = (
                            "pass_automated_only"
                            if result["checks"]["no_future_evidence"]
                            and result["citation_ids"]
                            and answer["status"] == "complete"
                            else "fail"
                        )
                    elif answer["status"] != "complete":
                        result["assessment"] = "fail"
                    # Absence of a code failure is not a semantic acceptance pass.
        except Exception as exc:
            result.update(
                status="error",
                assessment="fail",
                error_code=type(exc).__name__,
                error_detail=str(exc)[:1200],
            )
        result["latency_ms"] = (time.monotonic() - started) * 1000
        result["memory"] = memory.finish()
        result["api_calls"] = self.calls
        result["capability_coverage"] = capability_coverage(
            result, test["expected_tools"], self.corpus.policy["capability_map"]
        )
        if result["assessment"] in {"pass_automated_only", "needs_review"} and any(
            item["fulfilled"] is False
            for item in result["capability_coverage"].values()
        ):
            result["assessment"] = "fail_capability_coverage"
        result["latency_limit_s"] = test.get("max_latency_s")
        result["latency_limit_pass"] = (
            result["latency_ms"] <= test["max_latency_s"] * 1000
            if test.get("max_latency_s")
            else None
        )
        if result["latency_limit_pass"] is False:
            result["assessment"] = "fail"
        raw_path = self.output / (test["test_id"] + ".json")
        result["trace_path"] = str(raw_path.relative_to(ROOT))
        raw_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return result

    def _native(self, test: dict, result: dict) -> None:
        """Run the requested saved architecture on an existing genuine NASA engine history."""
        dataset = re.search(r"\bFD00[1-4]\b", test["prompt"]).group()
        alias = next(
            name
            for name in sorted(
                self.corpus.policy["model_aliases"], key=len, reverse=True
            )
            if name in test["prompt"]
        )
        model = self.corpus.policy["model_aliases"][alias]
        matches = [
            r
            for r in self.models
            if r["dataset"] == dataset
            and r["model_id"] == f"{dataset.lower()}-{model}-s42"
            and r["task"] == "rul"
        ]
        self.request("GET", "/predictions/models", params={"dataset": dataset})
        if not matches:
            result.update(
                status="blocked",
                assessment="fail",
                error_code="requested_architecture_unmapped",
                answer="No exact saved RUL architecture found; no model substitution made.",
            )
            return
        identifier = matches[0]["model_id"]
        response = self.request(
            "POST",
            "/intelligence/execute",
            json={
                "tool_id": "prediction.run",
                "arguments": {
                    "dataset": dataset,
                    "model_id": identifier,
                    "asset_id": dataset + "-ENGINE-001",
                },
            },
        )
        result["native_response"] = response.json()
        if response.status_code != 200:
            result.update(
                status="error",
                assessment="fail",
                error_code=response.json().get("error", {}).get("code"),
            )
            return
        body = response.json()
        prediction = body["result"]["prediction"]
        trace = self.request("GET", "/runs/" + body["run_id"] + "/trace").json()
        result.update(
            answer=json.dumps(prediction),
            tool_calls=[s["tool_id"] for s in trace["steps"]],
            model_identifiers=[prediction["provenance"]],
            citation_ids=body["result"]["evidence_ids"],
            trace=trace,
            mapping_note="Direct typed registry tool, not proof of natural-language architecture selection. Autoencoder maps explicitly to the preserved legacy RUL variant; experimental anomaly variant is not mislabeled as RUL.",
        )
        result["checks"] = {
            "dataset_id_correct": prediction["dataset"] == dataset,
            "model_id_correct": prediction["model_id"] == identifier,
            "real_artifact_used": bool(prediction["provenance"]["version"]),
            "finite_rul": math.isfinite(prediction["rul_cycles"]),
            "cycles_not_days": prediction["legacy_output"]["rul_unit"] == "cycles",
            "genuine_input": prediction["input_source_type"] == "nasa_simulation",
        }
        result["assessment"] = (
            "pass_automated_only" if all(result["checks"].values()) else "fail"
        )


def main() -> None:
    """Run P0 before P1/P2, preserve actual raw data and list unexecuted cases explicitly."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--priority", choices=["P0", "P1", "P2"], default="P0")
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    state = args.state.resolve()
    if not state.is_relative_to((ROOT / ".runtime/stress_lab").resolve()):
        raise SystemExit(
            "Use a disposable state directory under .runtime/stress_lab only"
        )
    state.mkdir(parents=True, exist_ok=True)
    report = audit(args.corpus)
    report.update(
        native_integrity_files=verify_integrity(),
        api_version="3.2.0",
        time_utc=datetime.now(timezone.utc).isoformat(),
    )
    report["source_sha256"] = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ["app", "config", "scripts/stress_lab"]
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and p.suffix in {".py", ".yaml"}
    }
    (state / ("audit-" + args.priority + ".json")).write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    if args.audit_only:
        print(json.dumps(report, indent=2))
        return
    policy = yaml.safe_load(
        (ROOT / "tests/stress_lab_config.yaml").read_text(encoding="utf-8")
    )
    corpus = PublicCorpus(args.corpus, state, policy)
    cases = [
        json.loads(line)
        for line in safe_fixture(args.corpus, "tests/test_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    if args.priority != "P0":
        preceding = "P0" if args.priority == "P1" else "P1"
        previous_path = state / (preceding + "_results.jsonl")
        previous = (
            {
                row["test_id"]
                for row in map(
                    json.loads, previous_path.read_text(encoding="utf-8").splitlines()
                )
            }
            if previous_path.is_file()
            else set()
        )
        if previous != {
            row["test_id"] for row in cases if row["priority"] == preceding
        }:
            raise SystemExit(
                "Finish/explicitly record every case in "
                + preceding
                + " before advancing priority"
            )
    chosen = [
        t
        for t in cases
        if t["priority"] == args.priority and (not args.ids or t["test_id"] in args.ids)
    ]
    results_path = state / (args.priority + "_results.jsonl")
    if results_path.exists() and not args.resume:
        raise SystemExit(
            "Results exist; preserve them and choose a new state or --resume"
        )
    seen = (
        {
            r["test_id"]
            for r in map(
                json.loads, results_path.read_text(encoding="utf-8").splitlines()
            )
        }
        if results_path.exists()
        else set()
    )
    model_cases = 0
    multiturn_cases = 0
    with TestClient(
        create_app(state_dir=state, probe_model=False), raise_server_exceptions=False
    ) as client:
        runner = Assessment(client, corpus, state / "traces" / args.priority)
        for test in chosen:
            if test["test_id"] in seen:
                continue
            heavy = test["category"] in {
                "image_vision",
                "adversarial_content",
                "general_chat",
                "speech_transcription",
                "video_frames",
                "document_parsing",
            }
            if (heavy and model_cases >= policy["max_model_cases_per_priority"]) or (
                test["category"] == "multiturn_context"
                and multiturn_cases >= policy["max_multiturn_cases"]
            ):
                result = {
                    "test_id": test["test_id"],
                    "priority": args.priority,
                    "category": test["category"],
                    "executed": False,
                    "status": "blocked",
                    "assessment": "not_run",
                    "error_code": "bounded_model_budget",
                    "latency_ms": 0,
                    "human_verification_needed": True,
                }
            else:
                result = runner.run_case(test)
                model_cases += int(heavy)
                multiturn_cases += int(test["category"] == "multiturn_context")
            with results_path.open("a", encoding="utf-8") as output:
                output.write(json.dumps(result, ensure_ascii=False) + "\n")
            save_scorecard(results_path)
            print(
                test["test_id"],
                args.priority,
                result["assessment"],
                round(result["latency_ms"] / 1000, 3),
                result.get("error_code", ""),
                flush=True,
            )
    print("RESULTS=" + str(results_path), flush=True)
