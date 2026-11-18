"""Scoped exact/semantic retrieval over actual source chunks, never similarity as proof."""

import re
from pathlib import Path
from threading import Event
from typing import Any
from app.storage.database import Store


def search(
    store: Store,
    conversation_id: str,
    query: str,
    attachment_ids: list[str] | None = None,
    mode: str = "auto",
    as_of: str | None = None,
    cancelled: Event | None = None,
) -> list[dict[str, Any]]:
    """Search only this conversation's indexed local document passages."""
    from app.knowledge import embeddings
    from app.simulation.repository import utc

    store.conversation(conversation_id)
    if mode not in {"auto", "lexical", "semantic", "hybrid"}:
        raise ValueError("Unknown retrieval mode")
    for identifier in attachment_ids or []:
        store.attachment(identifier, conversation_id)
    terms = set(re.findall(r"[\w]+(?:[.-][\w]+)*", query.lower())) - {
        "a",
        "an",
        "the",
        "and",
        "or",
        "for",
        "with",
        "this",
        "that",
        "these",
        "those",
        "what",
        "how",
        "can",
        "does",
        "do",
        "is",
        "are",
        "of",
        "to",
        "from",
        "about",
        "which",
        "please",
        "tell",
        "me",
        "in",
        "it",
        "its",
    }
    chunks = store.rows(
        "SELECT c.*,a.name,a.created_at FROM chunks c JOIN attachments a ON a.id=c.attachment_id WHERE c.conversation_id=? AND a.kind IN ('document','csv')",
        (conversation_id,),
    )
    chunks = [
        c
        for c in chunks
        if (not attachment_ids or c["attachment_id"] in attachment_ids)
        and (not as_of or utc(c["created_at"]) <= utc(as_of))
    ]
    from app.evidence.integrity import validate_chunks

    validate_chunks(store, conversation_id, chunks)
    ranked = []
    scores = {}
    retrieval = {
        "mode": "lexical",
        "scope": "Exact local source excerpts; relevance is not claim verification.",
    }
    lexical = {
        c["id"]: len(terms & set(re.findall(r"[\w]+(?:[.-][\w]+)*", c["text"].lower())))
        for c in chunks
    }
    use_semantic = mode in {"semantic", "hybrid"} or (
        mode == "auto" and not any(lexical.values())
    )
    if use_semantic and chunks and embeddings.readiness()["configured"]:
        from app.knowledge.semantic import rank

        scores, retrieval = rank(store, conversation_id, query, chunks, cancelled)
        retrieval["mode"] = "hybrid" if mode != "semantic" else "semantic"
    elif use_semantic:
        if mode in {"semantic", "hybrid"} and not embeddings.readiness()["configured"]:
            from app.core.errors import SireError

            raise SireError(
                "embedding_unavailable",
                "Requested semantic model is not configured; no semantic results substituted.",
                503,
            )
        retrieval["semantic_status"] = (
            "not configured"
            if not embeddings.readiness()["configured"]
            else "no scoped source chunks"
        )
    for chunk in chunks:
        if attachment_ids and chunk["attachment_id"] not in attachment_ids:
            continue
        score = lexical[chunk["id"]]
        name_terms = set(re.findall(r"[^\W_]+", Path(chunk["name"]).stem.lower()))
        name_matches = len(terms & name_terms)
        similarity = scores.get(chunk["id"])
        if (mode != "semantic" and score) or (
            similarity is not None
            and similarity >= embeddings.POLICY["minimum_similarity"]
        ):
            ranked.append(
                {
                    "id": chunk["id"],
                    "attachment_id": chunk["attachment_id"],
                    "source": chunk["name"],
                    "locator": chunk["locator"],
                    "excerpt": chunk["text"],
                    "lexical_matches": score,
                    "source_name_matches": name_matches,
                    "semantic_similarity": similarity,
                    "retrieval": retrieval,
                    "ranking_score": (
                        score
                        + name_matches * embeddings.POLICY.get("source_name_weight", 2)
                        if mode != "semantic"
                        else 0
                    )
                    + (similarity or 0),
                }
            )
    return sorted(
        ranked,
        key=lambda row: (-row["ranking_score"], -len(row["excerpt"]), row["id"]),
    )[: embeddings.POLICY["max_results"]]
