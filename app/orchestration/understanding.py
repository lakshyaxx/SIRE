"""Resolve user-declared scope without interpreting uploaded instructions as commands."""

import re
from app.investigation.schemas import EvidenceItem


def target_asset(question: str, evidence: list[EvidenceItem]) -> str | None:
    """Choose an explicit identifier, otherwise a single source-declared asset; never link assets."""
    named = set(
        re.findall(r"(?<![\w-])([A-Za-z][A-Za-z0-9_]*-\d[\w-]*)(?![\w-])", question)
    )
    known = {item.asset_identity for item in evidence if item.asset_identity}
    named |= {
        asset
        for asset in known
        if re.search(r"(?<![\w-])" + re.escape(asset) + r"(?![\w-])", question, re.I)
    }
    if named:
        return next(iter(named)) if len(named) == 1 else None
    return next(iter(known)) if len(known) == 1 else None
