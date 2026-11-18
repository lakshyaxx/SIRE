"""Bounded speech segmentation without changing source words or inventing audio."""

import re
from app.core.errors import SireError


def split_text(text: str, max_characters: int, max_chunks: int) -> list[str]:
    """Retain all words in sentence-aware bounded chunks; reject unsplittable tokens."""
    if max_characters < 1 or max_chunks < 1:
        raise ValueError("Positive chunk bounds required")
    result = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        pending = ""
        for word in sentence.split():
            if len(word) > max_characters:
                raise SireError(
                    "speech_token_limit",
                    "A text token exceeds the speech chunk budget.",
                    422,
                )
            if pending and len(pending) + 1 + len(word) > max_characters:
                result.append(pending)
                pending = ""
            pending = (pending + " " + word).strip()
        if pending:
            result.append(pending)
    if not result or len(result) > max_chunks:
        raise SireError(
            "speech_chunk_limit",
            "Text exceeds the bounded number of speech segments.",
            413,
        )
    return result
