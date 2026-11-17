"""Actual API refusal and explicit budget/inconclusive handling for reliability harness logic."""

from scripts.stress_lab.runner import Assessment
from scripts.stress_lab.reliability import run_reliability, run_load, run_multiturn
from scripts.stress_lab.server import create_probe_app
from fastapi.testclient import TestClient


def test_empty_message_probe_checks_real_validation(v2client, tmp_path):
    class Corpus:
        """No source fixtures are needed to test actual API validation."""

        policy = {"max_load_concurrency": 2}

    runner = Assessment(v2client, Corpus(), tmp_path)
    cid = runner.conversation("test-only-validation")
    result = {"checks": {}}
    run_reliability(runner, {"test_id": "TST-00510"}, result, cid)
    assert result["assessment"] == "pass_automated_only"
    assert runner.calls[-1]["status"] == 422


def test_high_load_request_is_explicitly_unrun(v2client, tmp_path):
    class Corpus:
        """A test-only explicit two-request limit."""

        policy = {"max_load_concurrency": 2}

    runner = Assessment(v2client, Corpus(), tmp_path)
    result = {}
    run_load(runner, {"prompt": "Execute 16 concurrent text_chat requests"}, result)
    assert result["assessment"] == "not_run" and not result["executed"]
    assert not runner.calls


def test_unrecognized_multiturn_contract_does_not_generate_fake_turns(
    v2client, tmp_path
):
    class Corpus:
        """No fixture interaction should occur for this malformed test definition."""

    runner = Assessment(v2client, Corpus(), tmp_path)
    result = {}
    run_multiturn(
        runner, {"prompt": "Test-only malformed turn declaration"}, result, "unused", {}
    )
    assert result["assessment"] == "not_run" and not runner.calls


def test_private_status_probe_is_json_not_spa_and_uses_disposable_state(tmp_path):
    with TestClient(create_probe_app(tmp_path / "isolated-network")) as client:
        response = client.get("/__stress_status")
        assert response.json() == {"active_jobs": 0, "active_conversations": 0}
        assert client.app.state.store.path.parent == tmp_path / "isolated-network"
