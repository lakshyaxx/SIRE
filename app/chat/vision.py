"""Canonical vision evidence and cache keys bound to file, question and actual model digest."""

import asyncio
import json
import time
from app.core.config import SETTINGS
from app.evidence.ledger import digest
from app.investigation.schemas import EvidenceItem
from app.orchestration.runtime import Invocation, Runner
from app.providers.adapter import OllamaAdapter
from app.providers.ollama import vision_policy_fingerprint
from app.storage.database import Store


async def inspect(
    store: Store,
    provider: OllamaAdapter,
    runner: Runner,
    item: dict,
    question: str,
    cancelled: asyncio.Event,
    locator: str | None = None,
) -> dict:
    """Inspect genuine bytes or reuse an exact saved inference; never reuse another question's result."""
    started = time.monotonic()
    from app.evidence.integrity import read_verified

    await asyncio.to_thread(read_verified, item)
    descriptor = next(
        (
            row
            for row in await asyncio.to_thread(provider.list_models)
            if row["name"] == SETTINGS["vision_model"]
        ),
        {},
    )
    fingerprint = descriptor.get("digest")
    key = digest(
        [
            item["sha256"],
            question,
            SETTINGS["vision_model"],
            fingerprint,
            vision_policy_fingerprint(),
        ]
    )
    cache = item["metadata"].get("vision_cache", {})
    cached = bool(fingerprint and key in cache)
    if cached:
        value = cache[key]
        async with runner.span("vision.inspect", [item["id"]]) as step:
            step["status"] = "cached"
            step["output_evidence_ids"] = value["evidence_ids"]
            step["model_provenance"] = {
                "provider": "ollama",
                "model": SETTINGS["vision_model"],
                "digest": fingerprint,
                "execution": "exact saved inference reused",
            }
    else:
        value = await runner.execute(
            Invocation(
                tool_id="vision.inspect",
                arguments={
                    "conversation_id": item["conversation_id"],
                    "attachment_id": item["id"],
                    "text": question
                    or "Describe visible features and limitations. Do not assume damage.",
                },
            ),
            cancelled,
        )
        cache[key] = value
        cache = dict(list(cache.items())[-3:])
        item["metadata"]["vision_cache"] = cache
        with store.connection() as db:
            db.execute(
                "UPDATE attachments SET metadata=? WHERE id=?",
                (json.dumps(item["metadata"]), item["id"]),
            )
    analysis = value["analysis"]
    return {
        "tool": {
            "tool": "vision.inspect",
            "status": "cached" if cached else "complete",
            "provider": analysis["provider"],
            "model": analysis["model"],
            "model_digest": fingerprint,
            "elapsed_seconds": time.monotonic() - started,
            "source_ids": value["evidence_ids"],
        },
        "evidence": [
            EvidenceItem(
                id=identifier,
                modality="video_frame" if locator else "image",
                kind="model_inference",
                source_id=item["id"],
                origin_id=item["metadata"].get("parent_attachment_id")
                or "image_content:" + item["sha256"],
                observation=observation,
                locator=locator or item["name"],
                reliability="medium",
                limitations=analysis["limitations"],
            )
            for identifier, observation in zip(
                value["evidence_ids"], analysis["visible_observations"]
            )
        ],
    }
