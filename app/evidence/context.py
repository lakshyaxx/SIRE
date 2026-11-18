"""Bounded model-facing source aliases with exact server-side canonical citation restoration."""

import json
import re
from collections import OrderedDict
from app.core.errors import SireError
from app.investigation.schemas import EvidenceItem


def compact(
    evidence: list[EvidenceItem],
    question: str,
    budget: int = 10000,
    *,
    observation_characters: int = 1000,
) -> tuple[dict, dict[str, str]]:
    """Keep actual excerpts/source grouping while replacing long opaque IDs only inside model input."""
    sources, mapping, groups, limits = [], {}, {}, []
    excerpted = []
    buckets: dict[str, list[EvidenceItem]] = OrderedDict()
    for item in evidence:
        buckets.setdefault(item.origin_id or item.source_id, []).append(item)
    # One source's many channels must not crowd out a selected image or document.
    # Keep a short second document account beside the first before filling
    # remaining space with more channels from one measurement origin.
    heads = {
        key: 2 if bucket[0].modality == "document" else 1
        for key, bucket in buckets.items()
    }
    balanced = [
        item for key, bucket in buckets.items() for item in bucket[: heads[key]]
    ]
    balanced.extend(
        bucket[heads[key] + index]
        for index in range(max((len(b) for b in buckets.values()), default=0))
        for key, bucket in buckets.items()
        if heads[key] + index < len(bucket)
    )
    for item in balanced:
        alias = "E" + str(len(sources) + 1)
        origin = (
            "unverified_user_claims"
            if item.kind == "user_claim"
            else item.origin_id or item.source_id
        )
        group = groups.setdefault(origin, "S" + str(len(groups) + 1))
        source = {
            "id": alias,
            "origin_group": group,
            "kind": item.kind,
            "modality": item.modality,
            "observation": item.observation[:observation_characters],
            "reliability": item.reliability,
        }
        for key in ["asset_identity", "predicate", "value", "locator"]:
            value = getattr(item, key)
            if value is not None:
                source[key] = value
        if (
            len(json.dumps(sources + [source], ensure_ascii=False))
            + min(len(question), 3000)
            > budget - 1000
        ):
            continue
        sources.append(source)
        mapping[alias] = item.id
        if len(item.observation) > observation_characters:
            excerpted.append(alias)
        limits.extend(item.limitations)
    return {
        "question": question[:3000],
        "untrusted_evidence": sources,
        "source_limitations": list(dict.fromkeys(limits))[:8],
        "citation_format": (
            "Use [E1], [E2], etc. only for the supplied source aliases. The server restores exact canonical references. Sources in one origin_group are correlated observations, not independent corroboration."
            if sources
            else "No external sources are supplied. Citations are not required for ordinary conversation. Do not invent source identifiers or citations."
        ),
        "selection": {
            "provided_sources": len(sources),
            "omitted_sources": len(evidence) - len(sources),
            "excerpted_sources": excerpted,
            "question_excerpted": len(question) > 3000,
        },
    }, mapping


def restore_text(
    text: str, mapping: dict[str, str], additional_known_ids: set[str] | None = None
) -> str:
    """Reject unknown source citations and expand validated short references without inventing IDs."""
    known = set(mapping.values()) | (additional_known_ids or set())
    for identifier in re.findall(
        r"\[((?:(?:EV|SRC):[a-fA-F0-9]{16,64})|(?:[a-fA-F0-9]{24})|(?:(?:prediction|user):[a-fA-F0-9]{32})|(?:[a-fA-F0-9]{32}:schema))\]",
        text,
    ):
        if identifier not in known:
            raise SireError(
                "unsupported_source_reference",
                "Model introduced a source reference not supplied to this response; its commentary was withheld.",
                503,
            )

    def expand(match: re.Match) -> str:
        alias = match.group(1).upper()
        if alias not in mapping:
            raise SireError(
                "unsupported_source_reference",
                "Model introduced an unknown source alias; its commentary was withheld.",
                503,
            )
        return "[" + mapping[alias] + "]"

    def separate(match: re.Match) -> str:
        references = re.findall(r"\bE\d+\b", match.group(1), re.I)
        if not references:
            return match.group()
        if "-" in match.group(1):
            raise SireError(
                "unsupported_source_reference",
                "Model returned an unsupported citation range; commentary withheld.",
                503,
            )
        return ", ".join("[" + reference.upper() + "]" for reference in references)

    text = re.sub(r"\[([^\]]*\bE\d+\b[^\]]*)\]", separate, text, flags=re.I)
    return re.sub(r"\[(E\d+)\]", expand, text, flags=re.I)
