"""HTTP contracts; test transport fixtures are never production response data."""

import json
import pytest


def test_crud_stream_and_restart(v2client):
    c = v2client.post("/api/v1/conversations", json={}).json()
    response = v2client.post(
        "/api/v1/chat/message",
        json={"conversation_id": c["id"], "content": "Tell me a short story"},
    )
    assert response.status_code == 200
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert (
        "".join(e.get("text", "") for e in events if e["type"] == "delta")
        == "Test-only transport reply."
    )
    reopened = v2client.get("/api/v1/conversations/" + c["id"]).json()
    assert len(reopened["messages"]) == 2
    assert (
        v2client.patch(
            "/api/v1/conversations/" + c["id"], json={"title": "Renamed"}
        ).status_code
        == 200
    )
    assert v2client.delete("/api/v1/conversations/" + c["id"]).status_code == 409
    assert (
        v2client.delete(
            "/api/v1/conversations/" + c["id"] + "?confirm=true"
        ).status_code
        == 200
    )


def test_api_wrong_domain_and_invented_measurement(v2client):
    response = v2client.post(
        "/api/v1/predictions/run",
        json={
            "dataset": "FD002",
            "model_id": "fd001-01_lightgbm-s42",
            "asset_id": "FD002-ENGINE-001",
        },
    )
    assert response.status_code == 422
    c = v2client.post("/api/v1/conversations", json={}).json()
    forged = {
        "question": "test",
        "conversation_id": c["id"],
        "evidence": [
            {
                "id": "fake",
                "modality": "inspection",
                "kind": "measurement",
                "source_id": "fake",
                "observation": "Test-only forged claim",
                "reliability": "high",
            }
        ],
    }
    assert v2client.post("/api/v1/investigations", json=forged).status_code == 422


@pytest.mark.parametrize("dataset", ["FD001", "FD002", "FD003", "FD004"])
def test_real_per_dataset_inference(v2client, dataset):
    models = v2client.get("/api/v1/predictions/models?dataset=" + dataset).json()[
        "models"
    ]
    selected = next(m for m in models if m["default"])
    response = v2client.post(
        "/api/v1/predictions/run",
        json={
            "dataset": dataset,
            "model_id": selected["model_id"],
            "asset_id": f"{dataset}-ENGINE-001",
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert (
        result["dataset"] == dataset
        and result["rul_cycles"] == result["legacy_output"]["rul"]
    )
    assert result["provenance"]["artifact_dir"].find(dataset) >= 0
    assert (
        v2client.get("/api/v1/predictions/results/" + result["id"]).status_code == 200
    )


def test_unknown_id_and_corrupt_upload(v2client):
    assert v2client.get("/api/v1/conversations/no-such-id").status_code == 404
    c = v2client.post("/api/v1/conversations", json={}).json()
    result = v2client.post(
        "/api/v1/attachments",
        data={"conversation_id": c["id"]},
        files={"file": ("../../bad.png", b"invalid", "image/png")},
    )
    assert result.status_code == 422
    assert "path" not in result.json()["error"]["details"]
