"""Offline evaluator: the only reader of hidden synthetic ground truth."""

import argparse
import asyncio
import json
import sqlite3
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.evidence.ledger import Ledger
from app.storage.database import Store
from app.simulation.generator import seed_scenarios, timestamp
from app.simulation.repository import Observations
from app.investigation.facility import investigate_facility, rank
from app.temporal.analytics import summarize, chronology


async def evaluate(directory: Path, seeds: list[int]) -> dict:
    """Compare actual outputs/alerts to isolated truth, disclosing N and toy-model limits."""
    results = []
    for seed in seeds:
        target = directory / f"seed-{seed}"
        seed_scenarios(target / "scenarios", seed)
        repo = Observations(target / "scenarios")
        ledger = Ledger(Store(target / "evaluation.sqlite3"))
        with sqlite3.connect(target / "scenarios/evaluator_truth.sqlite3") as truth_db:
            truth = {
                r[0]: json.loads(r[1])
                for r in truth_db.execute(
                    "SELECT scenario_id,payload FROM scenario_truth"
                )
            }
        for scenario in repo.scenarios():
            sid = scenario["id"]
            expected = truth[sid]
            case = await investigate_facility(
                repo,
                ledger,
                sid,
                scenario["asset_id"],
                scenario["reference_at"],
                asyncio.Event(),
            )
            ids = [h["id"] for h in case["hypotheses"]]
            labels = set(expected["mechanisms"])
            valid = 0
            for identifier in case["evidence_ids"]:
                e = ledger.resolve(identifier)["evidence"]
                valid += (
                    e["observed_at"] <= case["as_of"]
                    and e["available_at"] <= case["as_of"]
                )
            first_warning = None
            first_simple = None
            for hour in [24, 48, 60, 72, 84, 96]:
                cutoff = timestamp(hour)
                summaries = [
                    summarize(repo, ledger, sid, a["id"], cutoff)
                    for a in repo.assets(sid)
                ]
                ranked = rank(
                    summaries,
                    chronology(
                        repo, ledger, sid, cutoff, [a["id"] for a in repo.assets(sid)]
                    ),
                )
                if first_warning is None and any(
                    h["status"] == "supported" for h in ranked
                ):
                    first_warning = hour
                simple = any(
                    r["available"]
                    and r["delta"] is not None
                    and (
                        (c == "vibration" and r["delta"] > 1.2)
                        or (
                            c in {"bearing_temp", "winding_temp", "discharge_temp"}
                            and r["delta"] > 12
                        )
                    )
                    for s in summaries
                    for c, r in s["channels"].items()
                )
                if first_simple is None and simple:
                    first_simple = hour
            results.append(
                {
                    "seed": seed,
                    "scenario_id": sid,
                    "known_mechanisms": sorted(labels),
                    "control": expected["control"],
                    "abstain_expected": expected["abstain_expected"],
                    "top1_match": bool(labels and ids[0] in labels),
                    "top3_match": bool(labels & set(ids[:3])),
                    "contributor_recall": (
                        len(labels & set(case["possible_contributors"])) / len(labels)
                        if labels
                        else None
                    ),
                    "abstained": case["abstained"],
                    "citation_valid": valid,
                    "citation_total": len(case["evidence_ids"]),
                    "contradiction_links": sum(
                        len(h["contradictions"]) for h in case["hypotheses"]
                    ),
                    "latency_seconds": case["elapsed_seconds"],
                    "tool_calls": len(ledger.get("runs", case["run_id"])["steps"]),
                    "first_warning_hour": first_warning,
                    "lead_time_hours": (
                        96 - first_warning
                        if labels and first_warning is not None
                        else None
                    ),
                    "simple_threshold_first_warning_hour": first_simple,
                }
            )
    labeled = [r for r in results if r["known_mechanisms"]]
    controls = [r for r in results if r["control"]]
    ambiguous = [r for r in results if r["abstain_expected"]]
    latencies = [r["latency_seconds"] for r in results]
    return {
        "N": len(results),
        "seeds": seeds,
        "engine": "deterministic_sire_facility_rules_1",
        "provider": "none; no LLM efficacy measured",
        "top1": {"correct": sum(r["top1_match"] for r in labeled), "N": len(labeled)},
        "top3": {"correct": sum(r["top3_match"] for r in labeled), "N": len(labeled)},
        "citation_validity": {
            "valid": sum(r["citation_valid"] for r in results),
            "total": sum(r["citation_total"] for r in results),
        },
        "normal_false_warnings": {
            "count": sum(r["first_warning_hour"] is not None for r in controls),
            "N": len(controls),
        },
        "ambiguous_abstention": {
            "correct": sum(r["abstained"] for r in ambiguous),
            "N": len(ambiguous),
        },
        "mean_latency_seconds": statistics.mean(latencies),
        "p95_latency_seconds": (
            statistics.quantiles(latencies, n=20, method="inclusive")[18]
            if len(latencies) >= 20
            else None
        ),
        "timeouts": sum(r.get("error") == "timeout" for r in results),
        "limitations": [
            "Small engineered synthetic benchmark, not independent physical validation or LLM accuracy.",
            "Case rule catalogue and generator were designed together; results are an integration benchmark.",
            "Lead time is on a coarse synthetic hourly grid, evaluated at six prefixes.",
            "No natural-language unsupported-claim rate was measured.",
        ],
        "cases": results,
    }


def main() -> None:
    """Write measured JSON/Markdown evaluation; never load truth in an API process."""
    p = argparse.ArgumentParser()
    p.add_argument("--directory", type=Path, default=ROOT / ".runtime/v3_evaluation")
    p.add_argument("--seeds", type=int, nargs="+", default=[42, 43])
    args = p.parse_args()
    result = asyncio.run(evaluate(args.directory, args.seeds))
    args.directory.mkdir(parents=True, exist_ok=True)
    (args.directory / "results.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    report = [
        "# V3 scenario evaluation",
        "",
        json.dumps({k: v for k, v in result.items() if k != "cases"}, indent=2),
        "",
        "Per-case actual measurements are in .runtime/v3_evaluation/results.json. No ground-truth label is read by investigator/API/knowledge modules.",
        "",
        "| Seed | Scenario | Top-1 | Top-3 | Abstained | Lead hours | Tool calls |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    report += [
        f"| {r['seed']} | {r['scenario_id']} | {r['top1_match']} | {r['top3_match']} | {r['abstained']} | {r['lead_time_hours']} | {r['tool_calls']} |"
        for r in result["cases"]
    ]
    (ROOT / "docs/EVALUATION_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}, indent=2))


if __name__ == "__main__":
    main()
