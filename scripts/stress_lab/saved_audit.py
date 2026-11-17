"""Read persisted actual replies/traces, including multi-turn/load paths omitted by initial flattening."""

import argparse
import hashlib
import json
from pathlib import Path
from app.core.config import ROOT
from app.evidence.ledger import EvidenceRecord, digest
from scripts.stress_lab.corpus import read_only, safe_fixture
from scripts.stress_lab.evaluation import verify_snapshot


def message_references(metadata: dict) -> list[str]:
    """Collect real metadata references without inferring sources from generated prose."""
    return list(
        dict.fromkeys(
            metadata.get("workspace", {}).get("evidence_ids", [])
            + [row["id"] for row in metadata.get("evidence", []) if row.get("id")]
        )
    )


def audit_saved(
    answers: Path, state: Path, continuation: Path, corpus: Path, output: Path
) -> dict:
    """Read existing assessment databases only; never create answers, execute models or change state."""
    if not output.resolve().is_relative_to((ROOT / ".runtime/stress_lab").resolve()):
        raise ValueError("Use the disposable assessment output namespace")
    output.mkdir(exist_ok=False)
    (output / "traces").mkdir()
    (output / "evidence").mkdir()
    source = safe_fixture(corpus, "facility/sire_synthetic_facility.sqlite3")
    rows = [
        json.loads(line) for line in answers.read_text(encoding="utf-8").splitlines()
    ]
    summary = {
        "cases": 0,
        "saved_assistant_messages": 0,
        "additional_snapshot_checks": 0,
        "supported_snapshot_checks": 0,
        "future_violations": 0,
        "legacy_references_unchecked": 0,
        "scope": "Read-only persisted actual output/trace recovery, not a rerun or replacement grade. Additional checks exclude IDs already checked in original rows. Legacy aliases are recorded without causing new compatibility snapshots. No models/private labels loaded.",
    }
    with (output / "saved_outputs.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            if not row.get("executed"):
                continue
            directory = (
                continuation if row.get("continuation_of_answers_sha256") else state
            )
            cids = list(
                dict.fromkeys(
                    ([row["conversation_id"]] if row.get("conversation_id") else [])
                    + [
                        r["conversation_id"]
                        for r in row.get("load_metrics", {}).get("requests", [])
                    ]
                    + [
                        r["conversation_id"]
                        for r in row.get("independent_sessions", [])
                    ]
                )
            )
            recovered = []
            checks = []
            already = {c["evidence_id"] for c in row.get("citation_checks", [])}
            checked = set()
            with read_only(directory / "sire.sqlite3") as db:
                for cid in cids:
                    for saved in db.execute(
                        "SELECT id,content,status,metadata,created_at FROM messages WHERE conversation_id=? AND role='assistant' ORDER BY created_at,rowid",
                        (cid,),
                    ):
                        saved = dict(saved)
                        meta = json.loads(saved.pop("metadata"))
                        references = message_references(meta)
                        run_id = meta.get("orchestration", {}).get("run_id")
                        run = (
                            db.execute(
                                "SELECT payload FROM v3_runs WHERE id=?", (run_id,)
                            ).fetchone()
                            if run_id
                            else None
                        )
                        trace = json.loads(run[0]) if run else None
                        recovered.append(
                            {
                                **saved,
                                "conversation_id": cid,
                                "metadata": meta,
                                "citation_ids": references,
                                "trace": trace,
                                "model_identifiers": [
                                    s["model_provenance"]
                                    for s in (trace or {}).get("steps", [])
                                    if s.get("model_provenance")
                                ],
                            }
                        )
                        cutoff = (
                            meta.get("workspace", {}).get("context", {}).get("as_of")
                        )
                        for identifier in references:
                            key = (identifier, cutoff)
                            if identifier in already or key in checked:
                                continue
                            checked.add(key)
                            if not identifier.startswith("EV:"):
                                summary["legacy_references_unchecked"] += 1
                                continue
                            item = db.execute(
                                "SELECT payload FROM v3_evidence WHERE id=?",
                                (identifier,),
                            ).fetchone()
                            if item is None:
                                checks.append(
                                    {
                                        "evidence_id": identifier,
                                        "exists": False,
                                        "semantic_status": "unsupported",
                                        "time_fence": False,
                                    }
                                )
                                continue
                            evidence = EvidenceRecord.model_validate_json(item[0])
                            if (
                                digest(
                                    evidence.model_dump(
                                        exclude={"id", "sha256", "human_verified"}
                                    )
                                )
                                != evidence.sha256
                            ):
                                raise ValueError(
                                    "Persisted evidence failed its integrity seal"
                                )
                            payload = {"evidence": evidence.model_dump()}
                            check = verify_snapshot(payload, source, cutoff)
                            filename = (
                                hashlib.sha256(identifier.encode()).hexdigest()
                                + ".json"
                            )
                            snapshot = output / "evidence" / filename
                            if not snapshot.exists():
                                snapshot.write_text(
                                    json.dumps(payload, ensure_ascii=False),
                                    encoding="utf-8",
                                )
                            check["snapshot_path"] = str(snapshot.relative_to(ROOT))
                            checks.append(check)
            proof = {
                "test_id": row["test_id"],
                "original_trace_path": row.get("trace_path"),
                "saved_messages": recovered,
                "additional_citation_checks": checks,
                "scope": "Persisted actual answers may contain unsupported claims; recovery is not semantic acceptance.",
            }
            proof_path = output / "traces" / (row["test_id"] + ".json")
            proof_path.write_text(
                json.dumps(proof, ensure_ascii=False), encoding="utf-8"
            )
            stream.write(
                json.dumps(
                    {
                        "test_id": row["test_id"],
                        "saved_assistant_messages": len(recovered),
                        "trace_path": str(proof_path.relative_to(ROOT)),
                        "additional_citation_checks": checks,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            summary["cases"] += 1
            summary["saved_assistant_messages"] += len(recovered)
            summary["additional_snapshot_checks"] += len(checks)
            summary["supported_snapshot_checks"] += sum(
                c["semantic_status"].startswith("supported_") for c in checks
            )
            summary["future_violations"] += sum(not c["time_fence"] for c in checks)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    """Recover real persisted output from sealed assessment namespaces."""
    parser = argparse.ArgumentParser()
    for name in ["answers", "state", "continuation", "corpus", "output"]:
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            audit_saved(
                args.answers,
                args.state,
                args.continuation,
                args.corpus,
                args.output.resolve(),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
