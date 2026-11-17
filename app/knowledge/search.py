"""Real lexical retrieval with exact page/line citations; embeddings remain optional."""

import re
from typing import Any
from app.storage.database import Store


def search(
    store: Store,
    conversation_id: str,
    query: str,
    attachment_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search only this conversation's indexed local document passages."""
    terms = set(re.findall(r"[\w]{3,}", query.lower()))
    chunks = store.rows(
        "SELECT c.*,a.name FROM chunks c JOIN attachments a ON a.id=c.attachment_id WHERE c.conversation_id=?",
        (conversation_id,),
    )
    ranked = []
    for chunk in chunks:
        if attachment_ids and chunk["attachment_id"] not in attachment_ids:
            continue
        score = len(terms & set(re.findall(r"[\w]{3,}", chunk["text"].lower())))
        if score:
            ranked.append(
                {
                    "id": chunk["id"],
                    "attachment_id": chunk["attachment_id"],
                    "source": chunk["name"],
                    "locator": chunk["locator"],
                    "excerpt": chunk["text"],
                    "lexical_matches": score,
                }
            )
    return sorted(ranked, key=lambda row: (-row["lexical_matches"], row["id"]))[:4]
