"""Small local SQLite store for conversations, evidence and immutable prediction records."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.core.errors import SireError


def now() -> str:
    """Return a real UTC event timestamp."""
    return datetime.now(timezone.utc).isoformat()


class Store:
    """Use short transactions and parameterized queries; never log message contents."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript(
                """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO schema_version VALUES(1);
            CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at TEXT,updated_at TEXT);
            CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,role TEXT,content TEXT,status TEXT,metadata TEXT,created_at TEXT);
            CREATE TABLE IF NOT EXISTS attachments(id TEXT PRIMARY KEY,conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,name TEXT,kind TEXT,mime TEXT,sha256 TEXT,path TEXT,metadata TEXT,created_at TEXT);
            CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY,attachment_id TEXT REFERENCES attachments(id) ON DELETE CASCADE,conversation_id TEXT,locator TEXT,text TEXT);
            CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,payload TEXT,created_at TEXT);
            CREATE TABLE IF NOT EXISTS predictions(id TEXT PRIMARY KEY,payload TEXT,created_at TEXT);
            CREATE INDEX IF NOT EXISTS message_conversation ON messages(conversation_id,created_at);
            """
            )

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Create a per-operation connection with foreign keys and a bounded lock wait."""
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def rows(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        """Run a fixed internal parameterized read query."""
        with self.connection() as db:
            return [dict(row) for row in db.execute(sql, args)]

    def create_conversation(self, title: str = "New chat") -> dict[str, Any]:
        """Persist an empty conversation and return its stable ID."""
        identifier, timestamp = uuid.uuid4().hex, now()
        with self.connection() as db:
            db.execute(
                "INSERT INTO conversations VALUES(?,?,?,?)",
                (identifier, title, timestamp, timestamp),
            )
        return self.conversation(identifier)

    def conversation(self, identifier: str) -> dict[str, Any]:
        """Resolve a conversation or return an explicit missing-ID error."""
        rows = self.rows("SELECT * FROM conversations WHERE id=?", (identifier,))
        if not rows:
            raise SireError("conversation_missing", "Conversation not found.", 404)
        return rows[0]

    def list_conversations(self) -> list[dict[str, Any]]:
        """List persisted conversations in most-recently-updated order."""
        return self.rows("SELECT * FROM conversations ORDER BY updated_at DESC")

    def rename(self, identifier: str, title: str) -> None:
        """Rename an existing conversation without changing its history."""
        self.conversation(identifier)
        with self.connection() as db:
            db.execute(
                "UPDATE conversations SET title=?,updated_at=? WHERE id=?",
                (title, now(), identifier),
            )

    def delete(self, identifier: str, confirmed: bool) -> list[str]:
        """Delete only after explicit confirmation; return owned attachment paths for cleanup."""
        if not confirmed:
            raise SireError(
                "confirmation_required", "Confirm conversation deletion.", 409
            )
        self.conversation(identifier)
        paths = [
            row["path"]
            for row in self.rows(
                "SELECT path FROM attachments WHERE conversation_id=?", (identifier,)
            )
        ]
        with self.connection() as db:
            db.execute("DELETE FROM conversations WHERE id=?", (identifier,))
        return paths

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        status: str = "complete",
        metadata: dict | None = None,
    ) -> str:
        """Append a message, retaining partial/error/cancelled states explicitly."""
        self.conversation(conversation_id)
        metadata = dict(metadata or {})
        metadata.setdefault(
            "source_type", "manually_entered" if role == "user" else "model_generated"
        )
        identifier, timestamp = uuid.uuid4().hex, now()
        with self.connection() as db:
            db.execute(
                "INSERT INTO messages VALUES(?,?,?,?,?,?,?)",
                (
                    identifier,
                    conversation_id,
                    role,
                    content,
                    status,
                    json.dumps(metadata or {}),
                    timestamp,
                ),
            )
            db.execute(
                "UPDATE conversations SET updated_at=? WHERE id=?",
                (timestamp, conversation_id),
            )
        return identifier

    def messages(self, identifier: str) -> list[dict[str, Any]]:
        """Read ordered messages including their persisted tool/citation metadata."""
        self.conversation(identifier)
        rows = self.rows(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at,rowid",
            (identifier,),
        )
        for row in rows:
            row["metadata"] = json.loads(row["metadata"])
        return rows

    def attachments(self, identifier: str) -> list[dict[str, Any]]:
        """Return local attachment metadata without revealing filesystem locations."""
        self.conversation(identifier)
        rows = self.rows(
            "SELECT * FROM attachments WHERE conversation_id=? ORDER BY created_at",
            (identifier,),
        )
        for row in rows:
            row.pop("path")
            row["metadata"] = json.loads(row["metadata"])
        return rows

    def attachment(
        self, identifier: str, conversation_id: str | None = None
    ) -> dict[str, Any]:
        """Resolve a stored attachment and enforce conversation membership."""
        rows = self.rows("SELECT * FROM attachments WHERE id=?", (identifier,))
        if not rows or (
            conversation_id and rows[0]["conversation_id"] != conversation_id
        ):
            raise SireError(
                "attachment_missing", "Attachment not found in this conversation.", 404
            )
        row = rows[0]
        row["metadata"] = json.loads(row["metadata"])
        return row

    def save_result(
        self, table: str, payload: dict, conversation_id: str | None = None
    ) -> str:
        """Persist only known result kinds, never execute a client-selected table name."""
        identifier = uuid.uuid4().hex
        payload["id"] = identifier
        with self.connection() as db:
            if table == "predictions":
                db.execute(
                    "INSERT INTO predictions VALUES(?,?,?)",
                    (identifier, json.dumps(payload), now()),
                )
            elif table == "cases":
                db.execute(
                    "INSERT INTO cases VALUES(?,?,?,?)",
                    (identifier, conversation_id, json.dumps(payload), now()),
                )
            else:
                raise ValueError("Unknown result kind")
        return identifier

    def result(self, table: str, identifier: str) -> dict:
        """Read a known result kind by opaque ID."""
        if table not in {"predictions", "cases"}:
            raise ValueError("Unknown result kind")
        rows = self.rows(f"SELECT payload FROM {table} WHERE id=?", (identifier,))
        if not rows:
            raise SireError("result_missing", "Saved result not found.", 404)
        return json.loads(rows[0]["payload"])
