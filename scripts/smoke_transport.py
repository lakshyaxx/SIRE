"""Real HTTP prediction-to-chat linkage, token cancellation and persisted partial-output probe."""

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main(base: str) -> None:
    """Call an actual saved FD003 model, then cancel real text after its first token."""
    result = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "base": base}
    with httpx.Client(base_url=base, timeout=320, trust_env=False) as client:
        result["health"] = client.get("/api/v1/health").raise_for_status().json()
        result["spa_routes"] = {
            path: client.get(path).status_code
            for path in [
                "/",
                "/chat",
                "/predictions",
                "/models",
                "/knowledge",
                "/settings",
                "/investigations",
            ]
        }
        cid = (
            client.post(
                "/api/v1/conversations",
                json={"title": "[verification] explicit prediction + cancel"},
            )
            .raise_for_status()
            .json()["id"]
        )
        result["conversation_id"] = cid
        prediction = (
            client.post(
                "/api/v1/predictions/run",
                json={
                    "dataset": "FD003",
                    "model_id": "fd003-01_lightgbm-s42",
                    "asset_id": "FD003-ENGINE-001",
                },
            )
            .raise_for_status()
            .json()
        )
        result["prediction"] = prediction
        request_id = uuid.uuid4().hex
        started = time.monotonic()
        events = []
        with client.stream(
            "POST",
            "/api/v1/chat/message",
            json={
                "conversation_id": cid,
                "request_id": request_id,
                "content": "Briefly interpret this explicitly attached NASA model result and its limitations.",
                "prediction_id": prediction["id"],
            },
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                events.append(event)
                if event["type"] == "delta" and "cancel" not in result:
                    result["first_token_seconds"] = time.monotonic() - started
                    result["cancel"] = (
                        client.post(
                            "/api/v1/chat/cancel", json={"request_id": request_id}
                        )
                        .raise_for_status()
                        .json()
                    )
        result["elapsed_seconds"] = time.monotonic() - started
        result["events"] = events
        history = client.get("/api/v1/conversations/" + cid).raise_for_status().json()
        result["history"] = history
        assert result["cancel"]["cancellation_requested"]
        assert events[-1]["type"] == "done" and events[-1]["status"] == "cancelled"
        assert history["messages"][-1]["status"] == "cancelled"
        assert history["messages"][-1]["content"]
        assert history["messages"][0]["metadata"]["prediction_id"] == prediction["id"]
        evidence = history["messages"][-1]["metadata"]["evidence"]
        assert any(item["id"] == "prediction:" + prediction["id"] for item in evidence)
    (ROOT / "docs/V2_TRANSPORT_EVIDENCE.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "rul_cycles": prediction["rul_cycles"],
                "cancelled": True,
                "first_token_seconds": result["first_token_seconds"],
                "elapsed_seconds": result["elapsed_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000")
