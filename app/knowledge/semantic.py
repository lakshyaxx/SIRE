"""Versioned case-isolated persistent vectors joined to current source chunks."""

import hashlib
import json
import math
from threading import Event
from app.core.errors import SireError
from app.knowledge import embeddings
from app.storage.database import Store


def migrate(store: Store) -> None:
    """Create only an additive derived index, retaining all source data and old rows."""
    with store.connection() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS semantic_chunks(conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,model_fingerprint TEXT NOT NULL,source_sha256 TEXT NOT NULL,vector_json TEXT NOT NULL,PRIMARY KEY(conversation_id,chunk_id,model_fingerprint))"
        )


def rank(
    store: Store,
    cid: str,
    query: str,
    chunks: list[dict],
    cancelled: Event | None = None,
) -> tuple[dict[str, float], dict]:
    """Rank actual scoped chunks without using another case's vectors or stale source text."""
    store.conversation(cid)
    if len(chunks) > embeddings.POLICY["max_index_chunks"]:
        raise SireError(
            "semantic_index_limit",
            "Too many source chunks; narrow the selected attachments.",
            413,
        )
    if not chunks:
        return {}, {"mode": "semantic", "indexed_chunks": 0}
    embeddings.model_files()
    migrate(store)
    version = embeddings.fingerprint()
    existing = {
        r["chunk_id"]: r
        for r in store.rows(
            "SELECT * FROM semantic_chunks WHERE conversation_id=? AND model_fingerprint=?",
            (cid, version),
        )
    }
    hashes = {
        c["id"]: hashlib.sha256((c["locator"] + "\0" + c["text"]).encode()).hexdigest()
        for c in chunks
    }
    missing = [
        c
        for c in chunks
        if c["id"] not in existing
        or existing[c["id"]]["source_sha256"] != hashes[c["id"]]
    ]
    result = embeddings.embed([c["text"] for c in missing] + [query], cancelled)
    with store.connection() as db:
        for c, vector in zip(missing, result["vectors"][:-1]):
            encoded = json.dumps(vector, allow_nan=False)
            db.execute(
                "INSERT OR REPLACE INTO semantic_chunks VALUES(?,?,?,?,?)",
                (cid, c["id"], version, hashes[c["id"]], encoded),
            )
            existing[c["id"]] = {
                "source_sha256": hashes[c["id"]],
                "vector_json": encoded,
            }
    q = result["vectors"][-1]
    scores = {}
    for c in chunks:
        # Refuse incomplete, tampered or dimension-incompatible derived cache rows.
        vector = json.loads(existing[c["id"]]["vector_json"])
        if len(vector) != len(q) or any(
            not isinstance(v, (float, int)) or not math.isfinite(v) for v in vector
        ):
            raise SireError(
                "semantic_index_integrity",
                "Derived vector cache is invalid; rebuild this case index.",
                503,
            )
        scores[c["id"]] = sum(a * b for a, b in zip(q, vector))
    return scores, {
        "mode": "semantic",
        "model": embeddings.POLICY["model_id"],
        "fingerprint": version,
        "indexed_chunks": len(chunks),
        "new_vectors": len(missing),
        "provider_metrics": {k: v for k, v in result.items() if k != "vectors"},
        "scope": "Similarity selects excerpts; it does not validate their claims.",
    }


def clear(store: Store, conversation_id: str) -> int:
    """Discard only this case's rebuildable derived index, never sources or research."""
    store.conversation(conversation_id)
    migrate(store)
    with store.connection() as db:
        return db.execute(
            "DELETE FROM semantic_chunks WHERE conversation_id=?", (conversation_id,)
        ).rowcount
