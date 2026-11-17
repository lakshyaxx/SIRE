"""Separate stdlib-only private-label evaluator. Never imports SIRE, models or ingestion.

Requires frozen answer hash and an external evaluator-approved mapping/label contract.
Prints aggregates only; labels, canaries, mappings and per-incident correctness stay private.
"""

import argparse
import hashlib
import json
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]


def evaluate(answers: Path, frozen: Path, labels: Path, contract: Path) -> dict:
    """Grade only sealed answers against explicitly approved externally isolated labels."""
    for private in [labels, contract]:
        if private.resolve().is_relative_to(REPOSITORY) or not private.is_file():
            raise ValueError(
                "Private evaluator inputs must exist outside application/repository roots"
            )
    seal = json.loads(frozen.read_text(encoding="utf-8"))
    body = answers.read_bytes()
    if hashlib.sha256(body).hexdigest() != seal["answers_sha256"]:
        raise ValueError("Answers changed after freeze; private evaluation refused")
    policy = json.loads(contract.read_text(encoding="utf-8"))
    if (
        policy.get("approved_by_evaluator") is not True
        or policy.get("multicause_policy") != "any_approved_cause"
    ):
        raise ValueError(
            "Evaluator approval and explicit any-approved-cause policy are required; no inferred alias mapping"
        )
    mapping = policy["engine_to_evaluator_cause"]
    rows = [
        json.loads(line) for line in body.decode("utf-8").splitlines() if line.strip()
    ]
    predictions = {
        row["incident_id"]: row
        for row in rows
        if row.get("category") == "historical_root_cause" and row.get("incident_id")
    }
    private_rows = [
        json.loads(line)
        for line in labels.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len({row["incident_id"] for row in private_rows}) != len(private_rows):
        raise ValueError("Duplicate private label identity; grading refused")
    counts = {
        "known_causes": 0,
        "top1_correct": 0,
        "top3_correct": 0,
        "negative_controls": 0,
        "false_positives": 0,
        "ambiguous_controls": 0,
        "missing_answers": 0,
    }
    splits = {}
    for label in private_rows:
        if label["split"] not in {"development", "validation", "holdout"}:
            raise ValueError("Unsupported evaluator split")
        split = splits.setdefault(label["split"], {key: 0 for key in counts})
        prediction = predictions.get(label["incident_id"])
        if prediction is None:
            counts["missing_answers"] += 1
            split["missing_answers"] += 1
        hypotheses = prediction.get("hypotheses", []) if prediction else []
        ranked = [mapping.get(h["id"]) for h in hypotheses]
        if label["case_type"] == "known_cause":
            allowed = set(label["cause_codes"])
            if not allowed:
                raise ValueError("Known-cause label has no approved causes")
            for values in [counts, split]:
                values["known_causes"] += 1
                values["top1_correct"] += bool(ranked and ranked[0] in allowed)
                values["top3_correct"] += bool(set(ranked[:3]) & allowed)
        elif label["case_type"] == "negative":
            positive = any(h.get("status") == "supported" for h in hypotheses)
            for values in [counts, split]:
                values["negative_controls"] += 1
                values["false_positives"] += positive
        elif label["case_type"] == "ambiguous":
            counts["ambiguous_controls"] += 1
            split["ambiguous_controls"] += 1
        else:
            raise ValueError("Unsupported evaluator case type")

    def rates(values: dict) -> dict:
        return {
            **values,
            "top1_rate": (
                values["top1_correct"] / values["known_causes"]
                if values["known_causes"]
                else None
            ),
            "top3_rate": (
                values["top3_correct"] / values["known_causes"]
                if values["known_causes"]
                else None
            ),
            "false_positive_rate": (
                values["false_positives"] / values["negative_controls"]
                if values["negative_controls"]
                else None
            ),
        }

    return {
        "status": "offline_evaluator_completed",
        "answers_sha256": seal["answers_sha256"],
        "aggregate": rates(counts),
        "by_split": {key: rates(value) for key, value in splits.items()},
        "policy": "Fixed original top1/top3 order, any externally approved cause counts. Negative warning means supported status, not mere tentative candidate. No private labels, mapping, incident-level correctness or canaries emitted.",
        "scope": "Synthetic public-corpus evaluation only, not real-equipment accuracy. No development/holdout labels entered SIRE or the engineering agent.",
    }


def main() -> None:
    """Run only after answer freeze; report refusal without echoing private values."""
    parser = argparse.ArgumentParser()
    for name in ["answers", "frozen", "labels", "contract", "output"]:
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(args.answers, args.frozen, args.labels, args.contract)
    except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        # Never echo private row contents or failing values.
        result = {
            "status": "blocked",
            "reason": "External evaluator inputs/approval contract unavailable or invalid",
            "error_type": type(exc).__name__,
        }
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] == "blocked":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
