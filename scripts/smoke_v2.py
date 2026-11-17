"""Real V2 HTTP/provider smoke evidence; no substituted predictions or generated observations."""

import json
import sys
import time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main(base: str) -> None:
    """Exercise real chat, image/doc intake and multi-hypothesis inference on labeled sources."""
    destination = ROOT / "docs/V2_LIVE_EVIDENCE.json"
    results = {}
    with httpx.Client(base_url=base, timeout=330, trust_env=False) as client:
        response = client.post(
            "/api/v1/conversations",
            json={"title": "[verification] V2 real-provider session"},
        )
        response.raise_for_status()
        cid = response.json()["id"]
        results["conversation_id"] = cid

        def save():
            destination.write_text(json.dumps(results, indent=2), encoding="utf-8")

        def message(
            name: str, content: str, attachments: list[str], mode: str = "chat"
        ) -> None:
            started = time.monotonic()
            events = []
            first = None
            with client.stream(
                "POST",
                "/api/v1/chat/message",
                json={
                    "conversation_id": cid,
                    "content": content,
                    "attachment_ids": attachments,
                    "mode": mode,
                },
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        event = json.loads(line[6:])
                        events.append(event)
                        if event["type"] == "delta" and first is None:
                            first = time.monotonic() - started
                        if event["type"] in {"tool", "error", "done"}:
                            print(
                                name,
                                event.get("type"),
                                event.get("tool"),
                                event.get("status"),
                                flush=True,
                            )
            results[name] = {
                "events": events,
                "elapsed_seconds": time.monotonic() - started,
                "first_token_seconds": first,
                "text": "".join(
                    e.get("text", "") for e in events if e["type"] == "delta"
                ),
            }
            save()

        message("hello", "Hi! Briefly explain what you can help with.", [])
        history = client.get("/api/v1/conversations/" + cid)
        history.raise_for_status()
        results["persisted_after_hello"] = len(history.json()["messages"])
        save()
        image = ROOT / "data/demo/bearing_cc0.jpg"
        with image.open("rb") as f:
            response = client.post(
                "/api/v1/attachments",
                data={"conversation_id": cid},
                files={"file": (image.name, f, "image/jpeg")},
            )
        response.raise_for_status()
        photo = response.json()
        results["photo"] = photo
        save()
        message(
            "image",
            "Describe only visible features. No defect is known in this public example bearing photograph.",
            [photo["id"]],
        )
        doc = ROOT / "data/knowledge/sire_model_card.md"
        with doc.open("rb") as f:
            response = client.post(
                "/api/v1/attachments",
                data={"conversation_id": cid},
                files={"file": (doc.name, f, "text/markdown")},
            )
        response.raise_for_status()
        document = response.json()
        results["document"] = document
        save()
        message(
            "document",
            "According to the attached project model card, can photographs prove internal damage or supply RUL? Cite the source.",
            [document["id"]],
        )
        message(
            "hypotheses",
            "No damage is established. Consider lubrication problems and misalignment as possible mechanisms for a hypothetical user report of noise. Compare them, cite actual observations or guidance, and identify missing discriminating tests. Do not invent a contradiction.",
            [photo["id"], document["id"]],
            "investigate",
        )
        results["final_history"] = client.get("/api/v1/conversations/" + cid).json()
        results["health"] = client.get("/api/v1/health").json()
        save()
        print("SAVED", destination, flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000")
