"""Actual deterministic specialist dispatch, case isolation and trace contracts."""

from pathlib import Path
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.providers import ollama
from app.chat.conversation import fast_route
from app.orchestration.planner import transcription_plan
import pytest


@pytest.mark.parametrize(
    "question", ["Hello, SIRE", "SIRE, hello!", "hi, bro", "Hello there", "hello! sire"]
)
def test_complete_addressed_greetings_use_fast_route(question: str) -> None:
    assert fast_route(question) == "social"


def test_greeting_prefix_does_not_swallow_an_engineering_request() -> None:
    assert fast_route("Hi, SIRE, explain the measured bearing vibration.") is None


def test_pure_transcription_route_does_not_swallow_compound_requests() -> None:
    attachments = [{"id": "TEST-ONLY-audio", "kind": "audio"}]
    assert (
        transcription_plan("Transcribe this recording.", attachments, "TEST-ONLY-case")
        .tools[0]
        .tool_id
        == "audio.transcript"
    )
    assert (
        transcription_plan(
            "Transcribe and investigate why it failed.", attachments, "TEST-ONLY-case"
        )
        is None
    )


def test_vision_policy_changes_invalidate_saved_observations(monkeypatch) -> None:
    previous = ollama.vision_policy_fingerprint()
    monkeypatch.setattr(
        ollama,
        "VISION_INSTRUCTIONS",
        ollama.VISION_INSTRUCTIONS + " TEST-ONLY policy change.",
    )
    assert previous != ollama.vision_policy_fingerprint()


def test_specialist_dispatch_uses_real_sources_and_shared_trace(tmp_path: Path) -> None:
    with TestClient(create_app(state_dir=tmp_path, probe_model=False)) as client:
        cid = client.post(
            "/api/v1/conversations", json={"title": "Test-only source isolation"}
        ).json()["id"]
        upload = client.post(
            "/api/v1/attachments",
            data={"conversation_id": cid},
            files={
                "file": (
                    "test-only.txt",
                    b"TEST-ONLY: inspect the lubrication system before recording observations.",
                )
            },
        )
        assert upload.status_code == 200, upload.text
        contracts = client.get("/api/v1/specialists/contracts").json()
        retrieve = next(
            t for t in contracts["tools"] if t["tool_id"] == "knowledge.retrieve"
        )
        assert "passages" in retrieve["output_schema"]["properties"]
        response = client.post(
            "/api/v1/specialists/execute",
            json={
                "request_id": "test-only-retrieval",
                "conversation_id": cid,
                "tool_id": "knowledge.retrieve",
                "arguments": {"text": "lubrication"},
            },
        )
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["status"] == "complete" and value["evidence_ids"]
        assert value["output"]["passages"][0]["excerpt"].startswith("TEST-ONLY:")
        trace = client.get("/api/v1/runs/" + value["run_id"] + "/trace").json()
        assert trace["status"] == "complete"
        assert [s["tool_id"] for s in trace["steps"]] == ["knowledge.retrieve"]
        other = client.post(
            "/api/v1/conversations", json={"title": "Other test-only case"}
        ).json()["id"]
        response = client.post(
            "/api/v1/specialists/execute",
            json={
                "request_id": "wrong-scope",
                "conversation_id": other,
                "tool_id": "knowledge.retrieve",
                "arguments": {"conversation_id": cid, "text": "lubrication"},
            },
        )
        assert response.status_code == 404
        assert not client.app.state.specialist_calls


def test_invalid_specialist_input_is_an_error_with_actual_failed_trace(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(state_dir=tmp_path, probe_model=False)) as client:
        cid = client.post("/api/v1/conversations", json={}).json()["id"]
        response = client.post(
            "/api/v1/specialists/execute",
            json={
                "request_id": "bad-input",
                "conversation_id": cid,
                "tool_id": "prediction.run",
                "arguments": {"dataset": "oil-rig"},
            },
        )
        assert response.status_code == 422
        body = response.json()
        assert body["status"] == "error" and body["output"] is None
        assert (
            client.get("/api/v1/runs/" + body["run_id"] + "/trace").json()["status"]
            == "error"
        )
        assert not client.app.state.specialist_calls
