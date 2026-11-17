"""Real loopback V3 showcase verification; transcripts never replaced with canned output."""

import argparse
import io
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import httpx
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Exercise real local text/image, fenced case/what-if/report and all four FD subsets."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8001")
    parser.add_argument("--skip-provider", action="store_true")
    args = parser.parse_args()
    destination = ROOT / "docs/V3_LIVE_SMOKE.json"
    result = {}

    def save() -> None:
        destination.write_text(json.dumps(result, indent=2), encoding="utf-8")

    with httpx.Client(base_url=args.base, timeout=310, trust_env=False) as c:
        result["health"] = c.get("/api/v1/health").raise_for_status().json()
        cid = (
            c.post(
                "/api/v1/conversations",
                json={"title": "[V3 verification] actual showcase"},
            )
            .raise_for_status()
            .json()["id"]
        )
        result["conversation_id"] = cid

        def chat(name: str, text: str, attachments: list[str]) -> None:
            started = time.monotonic()
            events = []
            with c.stream(
                "POST",
                "/api/v1/chat/message",
                json={
                    "conversation_id": cid,
                    "content": text,
                    "attachment_ids": attachments,
                },
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))
            result[name] = {
                "events": events,
                "elapsed_seconds": time.monotonic() - started,
            }
            save()
            assert (
                events[-1]["type"] == "done" and events[-1]["status"] == "complete"
            ), events[-1]
            print(name, "complete", result[name]["elapsed_seconds"], flush=True)

        if not args.skip_provider:
            chat(
                "text",
                "Hello. Briefly explain how evidence differs from a hypothesis.",
                [],
            )
            photo = ROOT / "data/demo/bearing_cc0.jpg"
            upload = (
                c.post(
                    "/api/v1/attachments",
                    data={"conversation_id": cid},
                    files={"file": (photo.name, photo.read_bytes(), "image/jpeg")},
                )
                .raise_for_status()
                .json()
            )
            chat(
                "image",
                "Describe only visible features and limitations in this licensed demonstration image. Do not assume a failure.",
                [upload["id"]],
            )
        scenarios = c.get("/api/v1/scenarios").raise_for_status().json()["scenarios"]
        s = next(s for s in scenarios if s["name"].endswith("01"))
        result["scenario_count"] = len(scenarios)
        cutoff = (
            datetime.fromisoformat(s["reference_at"]) - timedelta(hours=24)
        ).isoformat()
        scope = {"scenario_id": s["id"], "asset_id": s["asset_id"], "as_of": cutoff}
        rows = (
            c.get(
                f'/api/v1/assets/{s["asset_id"]}/telemetry',
                params={"scenario_id": s["id"], "as_of": cutoff, "limit": 5000},
            )
            .raise_for_status()
            .json()["records"]
        )
        assert rows and all(
            r["observed_at"] <= cutoff and r["available_at"] <= cutoff for r in rows
        )
        case = (
            c.post("/api/v1/facility/investigations", json=scope)
            .raise_for_status()
            .json()
        )
        result["case"] = case
        save()
        assert all(
            e["available_at"] <= cutoff and e["observed_at"] <= cutoff
            for e in case["timeline"]
        )
        for identifier in case["evidence_ids"]:
            c.get(
                "/api/v1/evidence/" + identifier, params={"as_of": cutoff}
            ).raise_for_status()
        result["trace"] = (
            c.get("/api/v1/runs/" + case["run_id"] + "/trace").raise_for_status().json()
        )
        what = (
            c.post(
                "/api/v1/simulations/what-if",
                json={"scenario_id": s["id"], "as_of": cutoff, "service_hour": 48},
            )
            .raise_for_status()
            .json()
        )
        result["what_if"] = what
        save()
        assert all(
            r["observed_at"] <= cutoff
            for item in what["comparison"]
            for r in item["trajectory"]
        )
        report = (
            c.post("/api/v1/cases/" + case["id"] + "/report", json={})
            .raise_for_status()
            .json()
        )
        pdf = c.get(
            "/api/v1/reports/" + report["id"] + "/download?format=pdf"
        ).raise_for_status()
        assert PdfReader(io.BytesIO(pdf.content)).pages
        out = ROOT / "output/v3"
        out.mkdir(exist_ok=True)
        (out / "live_engineering_report.pdf").write_bytes(pdf.content)
        result["report"] = {
            "metadata": report,
            "pdf_bytes": len(pdf.content),
            "pages": len(PdfReader(io.BytesIO(pdf.content)).pages),
        }
        result["predictions"] = []
        for dataset in ["FD001", "FD002", "FD003", "FD004"]:
            models = (
                c.get("/api/v1/predictions/models", params={"dataset": dataset})
                .raise_for_status()
                .json()["models"]
            )
            m = next(m for m in models if m["default"])
            prediction = (
                c.post(
                    "/api/v1/predictions/run",
                    json={
                        "dataset": dataset,
                        "model_id": m["model_id"],
                        "asset_id": dataset + "-ENGINE-001",
                    },
                )
                .raise_for_status()
                .json()
            )
            assert (
                prediction["dataset"] == dataset
                and prediction["rul_cycles"] is not None
            )
            result["predictions"].append(prediction)
            save()
            print(dataset, "actual cycles", prediction["rul_cycles"], flush=True)
        result["voice"] = c.get("/api/v1/voice/capabilities").raise_for_status().json()
        result["status"] = (
            "PASS for executed routes; voice/video unavailable and browser UI not tested"
        )
        save()
    print(result["status"])


if __name__ == "__main__":
    main()
