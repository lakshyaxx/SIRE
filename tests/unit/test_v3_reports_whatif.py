"""Same-seed intervention, real report content and deterministic PDF byte checks."""

import asyncio
import io
from pypdf import PdfReader
from app.evidence.ledger import Ledger
from app.investigation.facility import investigate_facility
from app.reports.engineering import create, pdf_bytes
from app.simulation.generator import seed_scenarios
from app.simulation.repository import Observations
from app.simulation.what_if import compare


def test_actual_intervention_and_reproducible_report(store, tmp_path):
    seed_scenarios(tmp_path / "scenarios", 42, [0])
    repo = Observations(tmp_path / "scenarios")
    s = repo.scenarios()[0]
    ledger = Ledger(store)
    result = compare(repo, ledger, s["id"], {"service_hour": 48})
    assert result["seed"] == 42 and result["label"] == "SIMULATED WHAT-IF"
    assert any(abs(r["difference"] or 0) > 0.1 for r in result["comparison"])
    assert (
        result["comparison"]
        == compare(repo, ledger, s["id"], {"service_hour": 48})["comparison"]
    )
    case = asyncio.run(
        investigate_facility(
            repo, ledger, s["id"], s["asset_id"], s["reference_at"], asyncio.Event()
        )
    )
    report = create(ledger, case["id"])
    again = create(ledger, case["id"])
    assert report == again and case["evidence_ids"][0] in report["markdown"]
    pdf = pdf_bytes(report)
    assert pdf == pdf_bytes(report)
    reader = PdfReader(io.BytesIO(pdf))
    assert reader.pages
    text = "\n".join(p.extract_text() for p in reader.pages)
    assert case["id"] in text and "SIMULATED" in text and "Heuristic" in text
    from app.knowledge.case_memory import annotate

    annotate(
        ledger,
        case["id"],
        "Test-only reviewer challenge; this is not measured evidence.",
        "human_reviewed_simulation",
    )
    reviewed = create(ledger, case["id"])
    assert (
        reviewed["id"] != report["id"]
        and reviewed["human_review_status"] == "human_reviewed_simulation"
    )
    assert (
        ledger.get("cases", case["id"])["confirmation_status"]
        == "simulation_unconfirmed"
    )
    assert ledger.get("reports", report["id"]) == report


def test_load_intervention_includes_affected_motor_and_fences_time(store, tmp_path):
    seed_scenarios(tmp_path / "scenarios", 42, [0])
    repo = Observations(tmp_path / "scenarios")
    scenario = repo.scenarios()[0]
    cutoff = scenario["reference_at"]
    result = compare(repo, Ledger(store), scenario["id"], {"load_factor": 0.8}, cutoff)
    motor = [row for row in result["comparison"] if row["asset_id"] == "MOTOR-401"]
    assert any(abs(row["difference"] or 0) > 1 for row in motor)
    assert all(
        point["observed_at"] <= cutoff
        for row in result["comparison"]
        for point in row["trajectory"]
    )
