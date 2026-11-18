"""Real compound jobs, duplicate data and fast-conversation coexistence in guarded QA state."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import time
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Run fresh actual cases; record output/traces without inventing diagnostic accuracy."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state = args.state_dir.resolve()
    out = args.output.resolve()
    if (
        not state.is_relative_to(ROOT / ".runtime")
        or state == ROOT / ".runtime/v2"
        or not out.is_relative_to(ROOT / ".runtime")
    ):
        raise SystemExit("Disposable state/output required")
    out.mkdir(exist_ok=False)
    proof = {
        "scope": "Actual local jobs and source invariants, not physical causal accuracy or evaluator-truth scoring.",
        "cases": [],
    }

    def save():
        (out / "results.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")

    with httpx.Client(
        base_url="http://127.0.0.1:8001/api/v1", timeout=310, trust_env=False
    ) as c:
        contract = c.get("/specialists/contracts")
        contract.raise_for_status()
        assert (
            contract.json()["state_namespace"]
            == hashlib.sha256(
                str((state / "sire.sqlite3").resolve()).encode()
            ).hexdigest()
        )
        for video in [False, True]:
            cid = c.post(
                "/conversations",
                json={
                    "title": "Disposable compound " + ("video" if video else "photo")
                },
            ).json()["id"]
            fixtures = []
            paths = [
                (
                    "media/video/bearing_inspection_pan.mp4"
                    if video
                    else "media/images/bearing_inspection_generated_01.jpg"
                ),
                "test_inputs/valid/telemetry_small.csv",
            ]
            if not video:
                paths.append("documents/facility_maintenance_handbook.pdf")
            for relative in paths:
                path = args.corpus / relative
                data = path.read_bytes()
                r = c.post(
                    "/attachments",
                    data={"conversation_id": cid},
                    files={"file": (path.name, data)},
                )
                r.raise_for_status()
                fixtures.append(
                    {
                        "relative_path": relative,
                        "source_sha256": hashlib.sha256(data).hexdigest(),
                        "receipt": r.json(),
                    }
                )
            if not video:
                rows = list(
                    csv.DictReader(
                        io.StringIO(
                            (
                                args.corpus / "test_inputs/valid/telemetry_small.csv"
                            ).read_text(encoding="utf-8-sig")
                        )
                    )
                )
                raw = json.dumps(rows).encode()
                r = c.post(
                    "/attachments",
                    data={"conversation_id": cid},
                    files={"file": ("TEST-ONLY-same-source-rows.json", raw)},
                )
                r.raise_for_status()
                duplicate = r.json()
                original = next(
                    f["receipt"]
                    for f in fixtures
                    if f["relative_path"].endswith(".csv")
                )
                assert (
                    duplicate["metadata"]["measurement_content_sha256"]
                    == original["metadata"]["measurement_content_sha256"]
                )
                fixtures.append(
                    {
                        "relative_path": "TEST-ONLY equivalent JSON encoding of original CSV rows, no changed values",
                        "source_sha256": hashlib.sha256(raw).hexdigest(),
                        "receipt": duplicate,
                    }
                )
            ids = [f["receipt"]["id"] for f in fixtures]
            began = time.perf_counter()
            r = c.post(
                "/investigation-jobs",
                json={
                    "conversation_id": cid,
                    "request_id": uuid.uuid4().hex,
                    "content": "Investigate alternative explanations for the supplied synthetic measurements and visually generated inspection fixture. Keep source and asset associations explicit and unverified where missing; a visual cannot prove hidden failure. Do not count repeated measurements as independent support.",
                    "attachment_ids": ids,
                    "mode": "investigate",
                },
            )
            r.raise_for_status()
            job = r.json()
            accepted = time.perf_counter() - began
            active = False
            for _ in range(100):
                resources = c.get("/runtime/resources").json()
                if resources["scheduler"]["active"]:
                    active = True
                    break
                status = c.get(
                    "/investigation-jobs/" + job["id"], params={"conversation_id": cid}
                ).json()
                if status["status"] not in {"queued", "running"}:
                    break
                time.sleep(0.1)
            start = time.perf_counter()
            r = c.post(
                "/chat/message",
                json={
                    "conversation_id": cid,
                    "content": "Hello, SIRE",
                    "request_id": uuid.uuid4().hex,
                },
            )
            r.raise_for_status()
            events = [
                json.loads(s[6:]) for s in r.text.splitlines() if s.startswith("data: ")
            ]
            greeting = {
                "seconds": time.perf_counter() - start,
                "heavy_active_when_requested": active,
                "events": events,
            }
            assert (
                active
                and events[-1]["status"] == "complete"
                and not events[-1]["metadata"].get("model_activity")
            ), greeting
            first_facts = None
            while True:
                job = c.get(
                    "/investigation-jobs/" + job["id"], params={"conversation_id": cid}
                ).json()
                if first_facts is None and any(
                    e.get("source") == "validated_descriptive_measurement_statistics"
                    for e in job["events"]
                ):
                    first_facts = time.perf_counter() - began
                if job["status"] not in {"queued", "running"}:
                    break
                if time.perf_counter() - began > 305:
                    c.post(
                        "/investigation-jobs/" + job["id"] + "/cancel",
                        params={"conversation_id": cid},
                        json={},
                    )
                    raise TimeoutError("Compound job exceeded bounded deadline")
                time.sleep(0.5)
            row = {
                "kind": "video_sensor" if video else "photo_pdf_csv_duplicate_json",
                "conversation_id": cid,
                "fixtures": fixtures,
                "accepted_seconds": accepted,
                "total_seconds": time.perf_counter() - began,
                "first_facts_poll_upper_bound": first_facts,
                "greeting_during_job": greeting,
                "job": job,
                "trace": c.get("/runs/" + job["run_id"] + "/trace").json(),
            }
            proof["cases"].append(row)
            save()
            print(
                json.dumps(
                    {
                        "kind": row["kind"],
                        "status": job["status"],
                        "seconds": row["total_seconds"],
                        "greeting_seconds": greeting["seconds"],
                    }
                ),
                flush=True,
            )
            assert job["status"] == "complete", job
        proof["resources_after"] = c.get("/runtime/resources").json()
        save()


if __name__ == "__main__":
    main()
