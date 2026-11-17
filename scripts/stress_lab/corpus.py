"""Validate public fixtures and map actual operational records to SIRE's observable contract."""

import hashlib
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from typing import Any

from app.simulation.repository import utc


def read_only(path: Path) -> sqlite3.Connection:
    """Open an existing public database without permitting writes or database creation."""
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def safe_fixture(root: Path, relative: str) -> Path:
    """Allow only contained public fixtures, never evaluator/private material or traversal."""
    target = (root / relative).resolve()
    if (
        not target.is_relative_to(root.resolve())
        or any(
            "evaluator" in part.casefold() or "private" in part.casefold()
            for part in Path(relative).parts
        )
        or not target.is_file()
    ):
        raise ValueError("Fixture leaves the public allowlist or is absent")
    return target


def audit(root: Path) -> dict[str, Any]:
    """Verify hashes, database integrity and all public incident/asset references first."""
    if (root / "evaluator_only").exists():
        raise ValueError(
            "Evaluator directory must be isolated externally before ingestion"
        )
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for record in manifest["files"]:
        path = safe_fixture(root, record["path"])
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != record["sha256"] or path.stat().st_size != record["size_bytes"]:
            raise ValueError("Public fixture integrity mismatch: " + record["path"])
    database = safe_fixture(root, "facility/sire_synthetic_facility.sqlite3")
    with read_only(database) as db:
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if any(
            "truth" in name.casefold() or "evaluator" in name.casefold()
            for name in tables
        ):
            raise ValueError(
                "Private table detected; do not expose database to investigator"
            )
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Public SQLite integrity failed")
        counts = {
            table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in sorted(tables)
        }
        violations = []
        for table in [
            "incidents",
            "events",
            "work_orders",
            "technician_logs",
            "alarms",
            "inspections",
            "fluid_samples",
            "telemetry",
        ]:
            bad = db.execute(
                f'SELECT COUNT(*) FROM "{table}" x LEFT JOIN assets a ON a.asset_id=x.asset_id WHERE a.asset_id IS NULL'
            ).fetchone()[0]
            if bad:
                violations.append({"table": table, "asset_orphans": bad})
            if table not in {"incidents", "telemetry"}:
                bad = db.execute(
                    f'SELECT COUNT(*) FROM "{table}" x LEFT JOIN incidents i ON i.incident_id=x.incident_id WHERE i.incident_id IS NULL'
                ).fetchone()[0]
                if bad:
                    violations.append({"table": table, "incident_orphans": bad})
        for field in ["from_asset", "to_asset"]:
            if db.execute(
                f"SELECT COUNT(*) FROM asset_dependencies e LEFT JOIN assets a ON e.{field}=a.asset_id WHERE a.asset_id IS NULL"
            ).fetchone()[0]:
                violations.append({"edge_field": field})
        duplicates = db.execute(
            "SELECT COUNT(*) FROM (SELECT asset_id,timestamp_utc,COUNT(*) n FROM telemetry GROUP BY asset_id,timestamp_utc HAVING n>1)"
        ).fetchone()[0]
        if violations or duplicates:
            raise ValueError(
                "Public reference/uniqueness failure: " + json.dumps(violations)
            )
    tests = [
        json.loads(line)
        for line in safe_fixture(root, "tests/test_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    if len({row["test_id"] for row in tests}) != len(tests):
        raise ValueError("Duplicate test identity")
    with safe_fixture(root, "tests/test_matrix.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        matrix = list(csv.DictReader(stream))
    indexed = {row["test_id"]: row for row in tests}
    if {row["test_id"] for row in matrix} != set(indexed) or any(
        row[key] != indexed[row["test_id"]][key]
        for row in matrix
        for key in ["category", "priority", "mode", "split"]
    ):
        raise ValueError("Test matrix differs from actual JSONL case inventory")
    for test in tests:
        for relative in test["attachments"]:
            safe_fixture(root, relative)
    return {
        "public_manifest_files": len(manifest["files"]),
        "hash_mismatches": 0,
        "reference_violations": 0,
        "duplicate_telemetry_keys": duplicates,
        "tables": counts,
        "test_cases": len(tests),
        "matrix_cases_verified": len(matrix),
        "evaluator_directory_present": False,
    }


class PublicCorpus:
    """Read only public evidence and lazily materialize isolated observable incident scopes."""

    def __init__(self, root: Path, state: Path, policy: dict) -> None:
        self.root, self.state, self.policy = root.resolve(), state.resolve(), policy
        self.source = safe_fixture(root, "facility/sire_synthetic_facility.sqlite3")
        self.source_sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        if (root / "evaluator_only").exists():
            raise ValueError("Unsafe public root contains evaluator material")
        self.directory = self.state / "scenarios"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "observations.sqlite3"
        with sqlite3.connect(self.path) as db:
            db.executescript(
                """
            CREATE TABLE IF NOT EXISTS scenarios(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS assets(scenario_id TEXT,id TEXT,payload TEXT,PRIMARY KEY(scenario_id,id));
            CREATE TABLE IF NOT EXISTS edges(scenario_id TEXT,source TEXT,target TEXT,payload TEXT);
            CREATE TABLE IF NOT EXISTS telemetry(scenario_id TEXT,asset_id TEXT,channel TEXT,observed_at TEXT,available_at TEXT,value REAL,unit TEXT,quality TEXT,source_type TEXT,source_record_id TEXT,source_field TEXT,source_sha256 TEXT,availability_basis TEXT,PRIMARY KEY(scenario_id,asset_id,channel,observed_at));
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,scenario_id TEXT,asset_id TEXT,observed_at TEXT,available_at TEXT,event_type TEXT,text TEXT,source_type TEXT,source_record_id TEXT,source_document_id TEXT,availability_basis TEXT);
            CREATE INDEX IF NOT EXISTS stress_window ON telemetry(scenario_id,asset_id,observed_at,channel);
            """
            )
        (self.state / "mapping_policy.json").write_text(
            json.dumps(
                {
                    "channel_map": policy["channel_map"],
                    "unit_map": policy["unit_map"],
                    "public_source_sha256": self.source_sha,
                    "asset_identity": "Original fixture identities retained; no demo-asset renaming",
                    "availability": "Telemetry/event record timestamps are declared same-time availability assumptions, not independently verified ingestion times. Work-order combined row uses closed_at. Lab analysis excluded from historical scope because analysis-availability timestamp is absent.",
                    "private_truth": "Not mounted or read; separate offline evaluator only",
                    "what_if": "No external-corpus causal simulator is supplied; do not substitute SIRE's built-in generator",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def incident(self, identifier: str) -> dict:
        """Return a whitelisted public incident, excluding any label-like metadata."""
        with read_only(self.source) as db:
            row = db.execute(
                "SELECT incident_id,asset_id,event_at,description,reported_severity,status FROM incidents WHERE incident_id=?",
                (identifier,),
            ).fetchone()
        if row is None:
            raise ValueError("Unknown public incident")
        return dict(row)

    def ensure_scope(self, identifier: str | None, asset_id: str | None) -> dict:
        """Convert actual source windows to the real app schema without inventing data."""
        sid = identifier or "stress-fleet"
        with sqlite3.connect(self.path) as db:
            previous = db.execute(
                "SELECT payload FROM scenarios WHERE id=?", (sid,)
            ).fetchone()
        if previous:
            scenario = json.loads(previous[0])
            return {
                "scenario_id": sid,
                "asset_id": asset_id or scenario["asset_id"],
                "as_of": scenario["reference_at"],
            }
        with read_only(self.source) as source, sqlite3.connect(self.path) as target:
            incident = self.incident(identifier) if identifier else None
            latest = source.execute(
                "SELECT MAX(timestamp_utc) FROM telemetry"
            ).fetchone()[0]
            reference = utc(incident["event_at"] if incident else latest)
            start = (
                datetime.fromisoformat(reference)
                - timedelta(
                    hours=(
                        self.policy["incident_window_hours"]
                        if incident
                        else self.policy["global_window_hours"]
                    )
                )
            ).isoformat()
            end = min(
                utc(latest),
                (
                    datetime.fromisoformat(reference)
                    + timedelta(hours=24 if incident else 0)
                ).isoformat(),
            )
            scenario = {
                "id": sid,
                "name": "SIMULATED stress corpus " + sid,
                "seed": self.policy["seed"],
                "generator_version": "external-stress-lab-1.0",
                "source_type": "sire_synthetic_scenario",
                "starts_at": start,
                "reference_at": reference,
                "ends_at": end,
                "asset_id": asset_id
                or (incident["asset_id"] if incident else "PUMP-001"),
                "public_incident": incident,
                "availability_warning": "Record-time availability assumed where corpus has no independent knowledge clock; lab analysis is excluded.",
            }
            target.execute(
                "INSERT INTO scenarios VALUES(?,?)", (sid, json.dumps(scenario))
            )
            assets = [dict(row) for row in source.execute("SELECT * FROM assets")]
            kinds = {row["asset_id"]: row["asset_type"] for row in assets}
            target.executemany(
                "INSERT INTO assets VALUES(?,?,?)",
                [
                    (
                        sid,
                        row["asset_id"],
                        json.dumps(
                            {
                                **row,
                                "id": row["asset_id"],
                                "scenario_id": sid,
                                "source_type": "sire_synthetic_scenario",
                            }
                        ),
                    )
                    for row in assets
                ],
            )
            for index, edge in enumerate(
                source.execute("SELECT * FROM asset_dependencies"), 1
            ):
                value = {
                    "scenario_id": sid,
                    "source": edge["from_asset"],
                    "target": edge["to_asset"],
                    "relation": edge["relation"],
                    "valid_from": start,
                    "valid_to": None,
                    "source_type": "sire_synthetic_scenario",
                    "original_record_id": f"asset_dependencies:row:{index}",
                    "validity_assumption": "Static supplied registry; independent installation timestamp unavailable",
                    "lag_minutes": edge["lag_minutes"],
                }
                target.execute(
                    "INSERT INTO edges VALUES(?,?,?,?)",
                    (sid, value["source"], value["target"], json.dumps(value)),
                )
            installed = {
                (row["asset_type"], row["field"])
                for row in source.execute("SELECT asset_type,field FROM sensor_catalog")
            }
            raw_start, raw_end = start.replace("+00:00", "Z"), end.replace(
                "+00:00", "Z"
            )
            cursor = source.execute(
                "SELECT rowid AS original_rowid,* FROM telemetry WHERE timestamp_utc>=? AND timestamp_utc<=? ORDER BY asset_id,timestamp_utc",
                (raw_start, raw_end),
            )
            count = 0
            while batch := cursor.fetchmany(500):
                converted = []
                for row in batch:
                    stamp = utc(row["timestamp_utc"])
                    for field, channel in self.policy["channel_map"].items():
                        if (kinds[row["asset_id"]], field) not in installed:
                            continue
                        converted.append(
                            (
                                sid,
                                row["asset_id"],
                                channel,
                                stamp,
                                stamp,
                                row[field],
                                self.policy["unit_map"][field],
                                row["quality_flag"],
                                "sire_synthetic_scenario",
                                f"telemetry:row:{row['original_rowid']}",
                                field,
                                self.source_sha,
                                "record_time_assumption_not_verified",
                            )
                        )
                target.executemany(
                    "INSERT INTO telemetry VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", converted
                )
                count += len(converted)
            # Read exact source records only; no inference from filename or hidden labels.
            specs = {
                "events": ("event_id", "timestamp_utc", "details"),
                "technician_logs": ("log_id", "timestamp_utc", "note"),
                "work_orders": ("work_order_id", "created_at", "technician_note"),
                "alarms": ("alarm_id", "timestamp_utc", None),
                "inspections": ("inspection_id", "timestamp_utc", "finding"),
            }
            event_count = 0
            for table, (pk, timestamp, text_field) in specs.items():
                for row in source.execute(
                    f'SELECT * FROM "{table}" WHERE "{timestamp}">=? AND "{timestamp}"<=?',
                    (raw_start, raw_end),
                ):
                    row = dict(row)
                    stamp = utc(row[timestamp])
                    available = utc(row.get("closed_at") or row[timestamp])
                    text = (
                        row.get(text_field, "")
                        if text_field
                        else json.dumps(row, ensure_ascii=False)
                    )
                    text = (
                        f"[{row[pk]} / {row.get('source_document_id',row[pk])}] " + text
                    )
                    target.execute(
                        "INSERT INTO events(scenario_id,asset_id,observed_at,available_at,event_type,text,source_type,source_record_id,source_document_id,availability_basis) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (
                            sid,
                            row["asset_id"],
                            stamp,
                            available,
                            row.get("event_type", table),
                            text,
                            "sire_synthetic_scenario",
                            row[pk],
                            row.get("source_document_id"),
                            (
                                "closed_at_for_combined_work_order"
                                if table == "work_orders"
                                else "record_time_assumption_not_verified"
                            ),
                        ),
                    )
                    event_count += 1
            record = {
                "scenario_id": sid,
                "telemetry_cells": count,
                "events": event_count,
                "start": start,
                "end": end,
                "source_sha256": self.source_sha,
            }
        with (self.state / "imported_scopes.jsonl").open(
            "a", encoding="utf-8"
        ) as output:
            output.write(json.dumps(record) + "\n")
        return {
            "scenario_id": sid,
            "asset_id": scenario["asset_id"],
            "as_of": reference,
        }
