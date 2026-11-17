"""Actual bounded reliability probes; missing capabilities remain explicit assessment gaps."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import uuid
from typing import TYPE_CHECKING
import httpx
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.core.config import ROOT, SETTINGS
from scripts.stress_lab.corpus import safe_fixture

if TYPE_CHECKING:
    from scripts.stress_lab.runner import Assessment


def normalized_chat(
    runner: "Assessment",
    result: dict,
    cid: str,
    prompt: str,
    scope: dict | None = None,
    selected: list[str] | None = None,
) -> None:
    """Save a real response/trace without elevating completion into semantic correctness."""
    answer = runner.chat(cid, prompt, selected or [], scope)
    result.update(
        raw_chat=answer,
        answer=answer.get("answer", ""),
        status="ok" if answer["status"] == "complete" else answer["status"],
        assessment="needs_review" if answer["status"] == "complete" else "fail",
        tool_calls=[s["tool_id"] for s in answer.get("trace", {}).get("steps", [])],
    )


def run_reliability(runner: "Assessment", test: dict, result: dict, cid: str) -> None:
    """Dispatch concrete robustness operations with exact API/source evidence."""
    identifier = int(test["test_id"].split("-")[1])
    request = runner.request
    checks = result["checks"]
    if identifier == 510:
        response = request(
            "POST", "/chat/message", json={"conversation_id": cid, "content": ""}
        )
        result["response"] = response.json()
        checks["empty_rejected"] = response.status_code == 422
    elif identifier == 511:
        scope = runner.corpus.ensure_scope("INC-0008", None)
        job = uuid.uuid4().hex
        with ThreadPoolExecutor(max_workers=1) as pool:
            began = time.monotonic()
            future = pool.submit(
                runner.chat,
                cid,
                "Investigate INC-0008 with the available evidence",
                [],
                scope,
                request_id=job,
            )
            time.sleep(0.2)
            cancelled = request("POST", "/chat/cancel", json={"request_id": job}).json()
            after = time.monotonic() - began
            answer = future.result(timeout=310)
        result.update(
            raw_chat=answer,
            answer=answer.get("answer", ""),
            cancellation_response=cancelled,
            cancellation_requested_after_seconds=after,
        )
        checks.update(
            cancel_within_second=after < 1,
            cancellation_accepted=cancelled["cancellation_requested"],
            cancelled_state=answer["status"] == "cancelled",
        )
    elif identifier == 512:
        path = safe_fixture(runner.corpus.root, "documents/maintenance_work_order.docx")
        content = path.read_bytes()
        items = [
            request(
                "POST",
                "/attachments",
                data={"conversation_id": cid},
                files={"file": (path.name, content)},
            ).json()
            for _ in range(2)
        ]
        result["duplicate_uploads"] = items
        checks["same_content_hash"] = items[0].get("sha256") == items[1].get("sha256")
        checks["deduplicated_source_identity"] = items[0].get("id") == items[1].get(
            "id"
        )
        result["limitation"] = (
            "Equal stored hashes alone do not implement duplicate-evidence merging."
        )
    elif identifier in {513, 519, 520, 521}:
        relative = {
            513: "documents/scanned_maintenance_note.pdf",
            519: "test_inputs/invalid/unsorted_duplicate_timestamps.csv",
            520: "test_inputs/invalid/mixed_units.csv",
            521: "test_inputs/adversarial/mixed_locale_timezones.csv",
        }[identifier]
        path = safe_fixture(runner.corpus.root, relative)
        response = request(
            "POST",
            "/attachments",
            data={"conversation_id": cid},
            files={"file": (path.name, path.read_bytes())},
        )
        result.update(
            fixture_ids=[
                {
                    "path": relative,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            ],
            response=response.json(),
            http_status=response.status_code,
        )
        checks["no_unhandled_failure"] = response.status_code < 500
        if identifier == 513:
            checks["explicit_no_ocr_error"] = (
                response.status_code == 422 or response.status_code == 400
            )
        else:
            result.update(
                assessment="needs_review",
                answer="Actual schema import response retained; safe generic text acceptance is not validated industrial semantics.",
            )
            return
    elif identifier == 514:
        response = request(
            "POST",
            "/predictions/run",
            json={
                "dataset": "FD001",
                "asset_id": "FD001-ENGINE-001",
                "model_id": "real_oilrig_rul_v99",
            },
        )
        checks["unknown_model_explicitly_rejected"] = response.status_code in {
            400,
            404,
            422,
        }
        result["response"] = response.json()
    elif identifier == 515:
        response = request(
            "POST",
            "/attachments",
            data={"conversation_id": cid},
            files={
                "file": (
                    "test-only-oversized.txt",
                    b"x" * (SETTINGS["max_upload_bytes"] + 65537),
                )
            },
        )
        checks["oversized_rejected"] = response.status_code == 413
        result.update(
            response=response.json(),
            limitation="Checks actual rejection and sampled memory. ASGI buffering transport does not establish network chunk/backpressure behavior.",
        )
    elif identifier == 516:
        scope = runner.corpus.ensure_scope("INC-0001", None)
        response = request(
            "GET",
            "/assets/AST-DOES-NOT-EXIST/telemetry",
            params={"scenario_id": scope["scenario_id"], "as_of": scope["as_of"]},
        )
        checks["unknown_asset_rejected"] = response.status_code == 404
        result["response"] = response.json()
    elif identifier == 525:
        before = request("GET", "/conversations/" + cid).json()
        with TestClient(
            create_app(state_dir=runner.corpus.state, probe_model=False),
            raise_server_exceptions=False,
        ) as restarted:
            after = restarted.get("/api/v1/conversations/" + cid).json()
        checks["restart_preserves_exact_conversation"] = before == after
        result["restart_scope"] = (
            "Real new ASGI application factory over saved SQLite; a new OS process was not required by this probe."
        )
    elif identifier == 526:
        result.update(
            network_disconnect=disconnect_probe(runner.corpus.state),
            assessment="needs_review",
        )
        checks["stream_jobs_cleaned"] = (
            result["network_disconnect"].get("cleanup", {}).get("active_jobs") == 0
        )
        checks["conversation_released"] = (
            result["network_disconnect"].get("cleanup", {}).get("active_conversations")
            == 0
        )
    elif identifier in {527, 528, 529, 530, 531}:
        scope = runner.corpus.ensure_scope("INC-0013", None)
        answer = runner.chat(
            cid, "Investigate INC-0013 and export an engineering report", [], scope
        )
        result.update(
            raw_chat=answer,
            answer=answer.get("answer", ""),
            tool_calls=[s["tool_id"] for s in answer.get("trace", {}).get("steps", [])],
        )
        workspace = answer.get("metadata", {}).get("workspace", {})
        case = workspace.get("outputs", {}).get("facility.investigate", {}).get("case")
        checks["actual_case_created"] = bool(case)
        if case and identifier in {527, 528, 530}:
            report = request("POST", "/cases/" + case["id"] + "/report", json={}).json()
            fmt = "markdown" if identifier == 528 else "pdf"
            response = request("GET", f"/reports/{report['id']}/download?format={fmt}")
            checks["report_content"] = response.status_code == 200 and (
                response.content.startswith(b"%PDF")
                if fmt == "pdf"
                else b"SIRE" in response.content
            )
            result["report_bytes"] = len(response.content)
            checks["citations_resolve"] = all(
                runner.request("GET", "/evidence/" + e).status_code == 200
                for e in case["evidence_ids"]
            )
            if identifier == 530:
                result.update(
                    assessment="needs_review",
                    limitation="Trusted local single-user app has no engineer/user authentication roles. Route access is not proof of role enforcement.",
                )
                return
        if case and identifier == 529:
            result["similar_cases"] = request(
                "GET", "/cases/" + case["id"] + "/similar"
            ).json()
            checks["explained_provisional_similarity"] = all(
                "caveat" in row for row in result["similar_cases"]["cases"]
            )
        if identifier == 531:
            checks["trace_saved_real_run"] = bool(answer.get("trace", {}).get("id"))
            result["limitation"] = (
                "Trace persisted from real calls; full independent source-level execution logging is not instrumented for every inner operation."
            )
    elif identifier == 532:
        result.update(
            status="blocked",
            assessment="not_run",
            executed=False,
            error_code="would_disrupt_shared_ollama",
            answer="The production app shares Ollama. This assessment will not stop or disable that shared runtime. Existing isolated outage regression coverage is separate from a new live outage test.",
        )
        return
    elif identifier == 533:
        scope = runner.corpus.ensure_scope("INC-0001", None)
        assets = request("GET", "/scenarios/INC-0001/assets").json()["assets"][:5]
        separate = []
        for index, asset in enumerate(assets):
            current = runner.conversation(test["test_id"] + "-" + str(index))
            selected_scope = {**scope, "asset_id": asset["id"]}
            answer = runner.chat(
                current,
                "Show sensor trends and available maintenance records. Session marker "
                + current,
                [],
                selected_scope,
            )
            separate.append(
                {
                    "conversation_id": current,
                    "status": answer["status"],
                    "run_id": answer.get("metadata", {})
                    .get("orchestration", {})
                    .get("run_id"),
                    "requested_asset_id": asset["id"],
                    "returned_asset_id": answer.get("metadata", {})
                    .get("workspace", {})
                    .get("context", {})
                    .get("asset_id"),
                }
            )
        result["independent_sessions"] = separate
        checks["unique_conversations"] = (
            len({r["conversation_id"] for r in separate}) == 5
        )
        checks["unique_runs"] = len({r["run_id"] for r in separate}) == 5
        checks["all_actual_complete"] = all(r["status"] == "complete" for r in separate)
        checks["asset_scopes_do_not_swap"] = all(
            r["requested_asset_id"] == r["returned_asset_id"] for r in separate
        )
        stored = [
            request("GET", "/conversations/" + row["conversation_id"]).json()
            for row in separate
        ]
        checks["no_cross_conversation_marker_in_saved_history"] = all(
            not any(
                other["conversation_id"] in json.dumps(conversation)
                for other in separate
                if other["conversation_id"] != row["conversation_id"]
            )
            for row, conversation in zip(separate, stored)
        )
    else:
        normalized_chat(runner, result, cid, test["prompt"])
        result["limitation"] = (
            "Underspecified procedural task tested as an ordinary actual request; missing evidence/action cannot be graded as completed from prose alone."
        )
        return
    result["assessment"] = (
        "pass_automated_only" if checks and all(checks.values()) else "fail"
    )
    result["answer"] = result.get("answer") or json.dumps(
        {"checks": checks, "response": result.get("response")}
    )


def disconnect_probe(state: Path) -> dict:
    """Use a genuine owned loopback server/client disconnect, then inspect actual private job counts."""
    from app.storage.database import Store

    directory = state / "network_probe"
    directory.mkdir(exist_ok=True)
    with socket.socket() as check:
        try:
            check.bind(("127.0.0.1", 8002))
        except OSError:
            return {
                "status": "blocked",
                "reason": "Port8002 already in use; unrelated process not touched",
            }
    env = dict(os.environ, SIRE_STATE_DIR=str(directory), PYTHONDONTWRITEBYTECODE="1")
    out = (directory / "server.log").open("ab")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "scripts.stress_lab.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8002",
        ],
        cwd=ROOT,
        env=env,
        stdout=out,
        stderr=out,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        with httpx.Client(
            base_url="http://127.0.0.1:8002", trust_env=False, timeout=12
        ) as client:
            for _ in range(40):
                try:
                    if client.get("/__stress_status").status_code == 200:
                        break
                except httpx.TransportError:
                    time.sleep(0.1)
            cid = (
                client.post(
                    "/api/v1/conversations",
                    json={"title": "Stress real stream disconnect"},
                )
                .raise_for_status()
                .json()["id"]
            )
            request_id = uuid.uuid4().hex
            received = []
            began = time.monotonic()
            with client.stream(
                "POST",
                "/api/v1/chat/message",
                json={
                    "conversation_id": cid,
                    "request_id": request_id,
                    "content": "Explain how to distinguish evidence from hypotheses in detail.",
                },
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        received.append(json.loads(line[6:]))
                        break
            time.sleep(0.5)
            cleanup = client.get("/__stress_status").raise_for_status().json()
            if cleanup["active_jobs"]:
                client.post("/api/v1/chat/cancel", json={"request_id": request_id})
            return {
                "status": "executed",
                "elapsed_seconds": time.monotonic() - began,
                "received_before_close": received,
                "cleanup": cleanup,
                "messages_after_close": Store(directory / "sire.sqlite3").messages(cid),
                "server_log": str((directory / "server.log").relative_to(ROOT)),
            }
    finally:
        if os.name == "nt" and process.poll() is None:
            # The Windows venv launcher can have a separate interpreter child.
            # Only this still-owned live process and its descendants are targeted.
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        elif process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        out.close()


def run_load(runner: "Assessment", test: dict, result: dict) -> None:
    """Execute only requested concurrency1/2, measuring actual durations/status/memory separately."""
    match = re.search(r"Execute (\d+) concurrent (\w+) requests", test["prompt"])
    count, action = int(match[1]), match[2]
    if count > runner.corpus.policy["max_load_concurrency"]:
        result.update(
            status="blocked",
            assessment="not_run",
            executed=False,
            error_code="concurrency_budget",
            answer="Requested load exceeds configured maximum2; no high-load job was started.",
        )
        return
    runner.corpus.ensure_scope("INC-0001", None)

    def execute(index: int) -> dict:
        began = time.monotonic()
        cid = runner.conversation(test["test_id"] + "-" + str(index))
        if action == "incident_lookup":
            response = runner.request("GET", "/scenarios/INC-0001")
            status = response.status_code
        elif action == "text_chat":
            answer = runner.chat(
                cid, "In one sentence, explain why evidence is needed.", []
            )
            status = 200 if answer["status"] == "complete" else 503
        elif action == "rul_inference":
            response = runner.request(
                "POST",
                "/predictions/run",
                json={
                    "dataset": "FD001",
                    "model_id": "fd001-01_lightgbm-s42",
                    "asset_id": "FD001-ENGINE-001",
                },
            )
            status = response.status_code
        else:
            relative = {
                "document_upload": "documents/facility_maintenance_handbook.pdf",
                "voice_transcription": "media/audio/pump_report_en.wav",
                "video_frames": "media/video/bearing_inspection_pan.mp4",
            }[action]
            path = safe_fixture(runner.corpus.root, relative)
            response = runner.request(
                "POST",
                "/attachments",
                data={"conversation_id": cid},
                files={"file": (path.name, path.read_bytes())},
            )
            body = response.json()
            status = (
                response.status_code
                if not body.get("metadata", {}).get("media_error")
                else 503
            )
        return {
            "conversation_id": cid,
            "status": status,
            "elapsed_ms": (time.monotonic() - began) * 1000,
        }

    with ThreadPoolExecutor(max_workers=count) as pool:
        runs = list(pool.map(execute, range(count)))
    times = sorted(row["elapsed_ms"] for row in runs)
    result.update(
        load_metrics={
            "requested_concurrency": count,
            "actual_requests": len(runs),
            "action": action,
            "p50_ms": sum(times) / len(times) if len(times) == 2 else times[0],
            "p95_nearest_rank_ms": times[max(0, math.ceil(0.95 * len(times)) - 1)],
            "errors": sum(r["status"] >= 400 for r in runs),
            "cancellations": 0,
            "requests": runs,
            "small_sample_warning": "Only1/2 requests; latency quantiles are descriptive, not a benchmark distribution.",
        },
        answer=json.dumps(runs),
        assessment=(
            "pass_automated_only" if all(r["status"] == 200 for r in runs) else "fail"
        ),
    )


def run_multiturn(
    runner: "Assessment", test: dict, result: dict, cid: str, scope: dict
) -> None:
    """Execute actual sequential turns; never manufacture the unspecified newly attached log."""
    questions = [part.strip() for part in re.split(r"Turn [123]:", test["prompt"])[1:]]
    if len(questions) != 3:
        result.update(
            executed=False,
            status="blocked",
            assessment="not_run",
            error_code="unknown_multiturn_fixture_contract",
        )
        return
    turns = []
    for question in questions:
        answer = runner.chat(cid, question, [], scope)
        turns.append(answer)
        scope = answer.get("metadata", {}).get("workspace", {}).get("context", scope)
    result.update(
        turns=turns,
        raw_chat=turns[-1],
        answer="\n\n".join(t.get("answer", "") for t in turns),
        tool_calls=[
            step["tool_id"]
            for turn in turns
            for step in turn.get("trace", {}).get("steps", [])
        ],
        assessment=(
            "needs_review" if all(t["status"] == "complete" for t in turns) else "fail"
        ),
        limitation="Fixture requests a newly attached log but attachments is empty. No log was invented; full evidence-driven revision acceptance is inconclusive. Actual three-turn context/answers/traces are retained.",
    )
    result["checks"]["same_incident_asset"] = all(
        (
            turn.get("metadata", {})
            .get("workspace", {})
            .get("context", scope)["scenario_id"]
            == scope["scenario_id"]
            and turn.get("metadata", {})
            .get("workspace", {})
            .get("context", scope)["asset_id"]
            == scope["asset_id"]
        )
        for turn in turns
    )
