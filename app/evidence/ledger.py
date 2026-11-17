"""Append-only, content-addressed evidence with explicit source types and resolvable pointers."""

import hashlib
import json
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.core.errors import SireError
from app.storage.database import Store, now

SourceType = Literal[
    "real_uploaded",
    "nasa_simulation",
    "sire_synthetic_scenario",
    "manually_entered",
    "model_generated",
]


def digest(value: Any) -> str:
    """Hash canonical finite JSON, rejecting NaN and infinity."""
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


class SourceRecord(BaseModel):
    """A source identity and authenticity statement, never a claim of verified truth."""

    model_config = ConfigDict(extra="forbid")
    id: str
    sha256: str
    source_type: SourceType
    mime: str = "application/json"
    name: str
    received_at: str
    authenticity: str = "unverified"
    privacy: str = "local_only"
    parser_version: str = "sire-evidence-1"
    asset_id: str | None = None
    scenario_id: str | None = None
    size_bytes: int | None = None
    storage_locator: str = "inline_snapshot"


class EvidenceRecord(BaseModel):
    """Immutable observation snapshot with event and information-availability times."""

    model_config = ConfigDict(extra="forbid")
    id: str
    source_id: str
    source_type: SourceType
    pointer: dict[str, Any]
    observation: dict[str, Any]
    observed_at: str | None = None
    available_at: str
    unit: str | None = None
    quality: str = "unreviewed"
    extraction_method: str
    human_verified: bool = False
    sha256: str


def migrate(store: Store) -> None:
    """Add V3 tables idempotently without modifying any V2 table or row."""
    with store.connection() as db:
        db.executescript(
            """
        CREATE TABLE IF NOT EXISTS v3_sources(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v3_evidence(id TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES v3_sources(id),payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v3_runs(id TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v3_cases(id TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v3_reports(id TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v3_annotations(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS v3_evidence_source ON v3_evidence(source_id);
        CREATE TRIGGER IF NOT EXISTS v3_evidence_no_update BEFORE UPDATE ON v3_evidence BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
        CREATE TRIGGER IF NOT EXISTS v3_evidence_no_delete BEFORE DELETE ON v3_evidence BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
        CREATE TRIGGER IF NOT EXISTS v3_source_no_update BEFORE UPDATE ON v3_sources BEGIN SELECT RAISE(ABORT,'immutable source'); END;
        CREATE TRIGGER IF NOT EXISTS v3_source_no_delete BEFORE DELETE ON v3_sources BEGIN SELECT RAISE(ABORT,'immutable source'); END;
        INSERT OR IGNORE INTO schema_version VALUES(3);
        """
        )


class Ledger:
    """Store exact observations; generated causal claims remain separate case records."""

    def __init__(self, store: Store) -> None:
        self.store = store
        migrate(store)

    def add(
        self,
        source_type: SourceType,
        name: str,
        observation: dict,
        pointer: dict,
        *,
        observed_at: str | None = None,
        available_at: str | None = None,
        asset_id: str | None = None,
        scenario_id: str | None = None,
        unit: str | None = None,
        quality: str = "unreviewed",
        method: str = "exact_source_snapshot",
        content_sha256: str | None = None,
        mime: str = "application/json",
        size_bytes: int | None = None,
        storage_locator: str = "inline_snapshot",
    ) -> EvidenceRecord:
        """Content-address source/record identities; re-reading unchanged facts is idempotent."""
        available = available_at or now()
        source_hash = content_sha256 or digest(observation)
        source_id = "SRC:" + digest(
            [source_type, name, source_hash, scenario_id, asset_id]
        )
        existing = self.store.rows(
            "SELECT payload FROM v3_sources WHERE id=?", (source_id,)
        )
        received = (
            json.loads(existing[0]["payload"])["received_at"] if existing else now()
        )
        if available_at is None:
            available = received
        source = SourceRecord(
            id=source_id,
            sha256=source_hash,
            source_type=source_type,
            name=name,
            received_at=received,
            mime=mime,
            size_bytes=size_bytes,
            storage_locator=storage_locator,
            asset_id=asset_id,
            scenario_id=scenario_id,
        )
        body = dict(
            source_id=source_id,
            source_type=source_type,
            pointer=pointer,
            observation=observation,
            observed_at=observed_at,
            available_at=available,
            unit=unit,
            quality=quality,
            extraction_method=method,
        )
        evidence_hash = digest(body)
        record = EvidenceRecord(id="EV:" + evidence_hash, sha256=evidence_hash, **body)
        with self.store.connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO v3_sources VALUES(?,?)",
                (source.id, source.model_dump_json()),
            )
            db.execute(
                "INSERT OR IGNORE INTO v3_evidence VALUES(?,?,?)",
                (record.id, source.id, record.model_dump_json()),
            )
        return record

    def resolve(self, identifier: str) -> dict:
        """Resolve an actual immutable record, validating its hash before returning it."""
        rows = self.store.rows(
            "SELECT payload FROM v3_evidence WHERE id=?", (identifier,)
        )
        if not rows:
            attachment = self.store.rows(
                "SELECT id,name,kind,mime,sha256,metadata,created_at FROM attachments WHERE id=?",
                (identifier,),
            )
            if attachment:
                item = attachment[0]
                metadata = json.loads(item["metadata"])
                record = self.add(
                    "real_uploaded",
                    item["name"],
                    {
                        key: item[key]
                        for key in ["id", "name", "kind", "mime", "sha256"]
                    },
                    {
                        "attachment_id": identifier,
                        "original_sha256": metadata.get("original_sha256"),
                        "stored_sha256": item["sha256"],
                    },
                    available_at=item["created_at"],
                    content_sha256=item["sha256"],
                    mime=item["mime"],
                    storage_locator="attachment:" + identifier,
                    quality="uploaded_source_authenticity_unverified",
                    method="attachment_metadata_snapshot_not_model_observation",
                )
                return {**self.resolve(record.id), "requested_alias": identifier}
            legacy = self.store.rows(
                "SELECT c.text,c.locator,c.attachment_id,a.name,a.sha256,a.created_at FROM chunks c JOIN attachments a ON a.id=c.attachment_id WHERE c.id=?",
                (identifier,),
            )
            if legacy:
                row = legacy[0]
                record = self.add(
                    "real_uploaded",
                    row["name"],
                    {"excerpt": row["text"]},
                    {"attachment_id": row["attachment_id"], "locator": row["locator"]},
                    available_at=row["created_at"],
                    content_sha256=row["sha256"],
                    quality="user_supplied_unverified",
                    method="v2_chunk_compatibility_snapshot",
                )
                return {**self.resolve(record.id), "requested_alias": identifier}
            if identifier.startswith("prediction:"):
                legacy = self.store.rows(
                    "SELECT payload,created_at FROM predictions WHERE id=?",
                    (identifier.removeprefix("prediction:"),),
                )
                if legacy:
                    value = json.loads(legacy[0]["payload"])
                    record = self.add(
                        "model_generated",
                        "Saved native prediction",
                        value,
                        {"prediction_id": identifier.removeprefix("prediction:")},
                        available_at=legacy[0]["created_at"],
                        method="v2_prediction_compatibility_snapshot",
                        quality="model_inference_unverified",
                    )
                    return {**self.resolve(record.id), "requested_alias": identifier}
            if identifier.startswith("user:"):
                legacy = self.store.rows(
                    "SELECT content,created_at FROM messages WHERE id=? AND role='user'",
                    (identifier.removeprefix("user:"),),
                )
                if legacy:
                    record = self.add(
                        "manually_entered",
                        "User claim",
                        {"claim": legacy[0]["content"]},
                        {"message_id": identifier.removeprefix("user:")},
                        available_at=legacy[0]["created_at"],
                        quality="user_claim_unverified",
                    )
                    return {**self.resolve(record.id), "requested_alias": identifier}
            saved = self.store.rows(
                "SELECT m.id,m.created_at,e.value FROM messages m, "
                "json_each(m.metadata,'$.evidence') e "
                "WHERE json_extract(e.value,'$.id')=? ORDER BY m.created_at,m.rowid LIMIT 1",
                (identifier,),
            )
            if saved:
                item = json.loads(saved[0]["value"])
                generated = item.get("kind") == "model_inference"
                record = self.add(
                    "model_generated" if generated else "real_uploaded",
                    item.get("locator") or "Saved chat evidence",
                    item,
                    {
                        "message_id": saved[0]["id"],
                        "original_evidence_id": identifier,
                        "attachment_id": item.get("source_id"),
                    },
                    available_at=saved[0]["created_at"],
                    quality=(
                        "model_inference_unverified"
                        if generated
                        else "user_supplied_unverified"
                    ),
                    method="v2_message_evidence_compatibility_snapshot",
                )
                return {**self.resolve(record.id), "requested_alias": identifier}
            raise SireError("evidence_missing", "Evidence ID not found.", 404)
        record = EvidenceRecord.model_validate_json(rows[0]["payload"])
        body = record.model_dump(exclude={"id", "sha256", "human_verified"})
        if digest(body) != record.sha256:
            raise SireError(
                "evidence_integrity", "Evidence integrity verification failed.", 503
            )
        source = self.store.rows(
            "SELECT payload FROM v3_sources WHERE id=?", (record.source_id,)
        )[0]
        return {
            "evidence": record.model_dump(),
            "source": json.loads(source["payload"]),
        }

    def save(
        self,
        kind: Literal["runs", "cases", "reports"],
        payload: dict,
        identifier: str | None = None,
    ) -> str:
        """Persist versioned results separately from immutable source observations."""
        if kind not in {"runs", "cases", "reports"}:
            raise ValueError("Unsupported object kind")
        identifier = identifier or str(uuid.uuid4())
        with self.store.connection() as db:
            db.execute(
                f"INSERT INTO v3_{kind} VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                (identifier, json.dumps(payload, allow_nan=False), now()),
            )
        return identifier

    def get(self, kind: Literal["runs", "cases", "reports"], identifier: str) -> dict:
        """Read a known V3 object kind, rejecting absent identities."""
        if kind not in {"runs", "cases", "reports"}:
            raise ValueError("Unsupported object kind")
        rows = self.store.rows(
            f"SELECT payload FROM v3_{kind} WHERE id=?", (identifier,)
        )
        if not rows:
            raise SireError("record_missing", "Record not found.", 404)
        return json.loads(rows[0]["payload"])
