"""Deterministic channel availability from immutable rows, separate from model sufficiency claims."""

import math
import re
from app.core.config import SETTINGS
from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.investigation.schemas import Case
from app.simulation.repository import utc


def inventory(case: Case, ledger: Ledger) -> list[dict]:
    """Enumerate actual good-quality source readings; a model summary cannot create availability."""
    result = []
    for item in case.evidence:
        if item.kind != "measurement":
            continue
        try:
            record = ledger.resolve(item.id)["evidence"]
        except SireError:
            continue
        if record["source_type"] == "model_generated" or (
            case.as_of and utc(record["available_at"]) > case.as_of
        ):
            continue
        grouped: dict[tuple, list] = {}
        for row in record["observation"].get("rows", []):
            asset = row.get("asset_id", record["pointer"].get("asset_id"))
            channel = row.get("channel", record["pointer"].get("channel"))
            if case.asset_id and asset != case.asset_id:
                continue
            if case.as_of and (
                utc(row["observed_at"]) > case.as_of
                or utc(row.get("available_at", record["available_at"])) > case.as_of
            ):
                continue
            value = row.get("value")
            if (
                row.get("quality", "good") != "good"
                or isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                continue
            if asset and channel:
                grouped.setdefault(
                    (asset, channel, row.get("unit", record["unit"])), []
                ).append(row)
        for (asset, channel, unit), rows in grouped.items():
            result.append(
                {
                    "asset_id": asset,
                    "channel": channel,
                    "unit": unit,
                    "good_count": len(rows),
                    "start": min(row["observed_at"] for row in rows),
                    "end": max(row["observed_at"] for row in rows),
                    "evidence_id": item.id,
                }
            )
    return sorted(
        result, key=lambda row: (row["asset_id"], row["channel"], row["evidence_id"])
    )


def check_absence(
    texts: list[str], available: list[dict], target_asset: str | None = None
) -> tuple[list[str], list[dict]]:
    """Correct explicit channel-absence assertions only; measurement adequacy stays unverified."""
    corrected, checks = [], []
    assets = {row["asset_id"] for row in available}
    default_asset = target_asset or (next(iter(assets)) if len(assets) == 1 else None)
    for text in texts:
        lowered = text.casefold()
        explicit_assets = {
            asset
            for asset in assets
            if re.search(
                r"(?<![\w-])" + re.escape(asset.casefold()) + r"(?![\w-])", lowered
            )
        }
        selected_asset = (
            next(iter(explicit_assets))
            if len(explicit_assets) == 1
            else default_asset if not explicit_assets else None
        )
        unknown_named = (
            set(re.findall(r"\b[A-Za-z][A-Za-z0-9_]*-\d[\w-]*\b", text)) - assets
        )
        if unknown_named:
            selected_asset = None
        absent = re.search(
            r"\b(?:no|missing|unavailable|absent|not (?:available|provided|recorded))\b",
            lowered,
        )
        measurement = re.search(
            r"\b(?:measurement|measurements|data|readings|telemetry|available|provided|recorded|delta)\b",
            lowered,
        )
        present = []
        if absent and measurement and selected_asset:
            for row in available:
                aliases = [
                    row["channel"].replace("_", " "),
                    *SETTINGS.get("measurement_channel_aliases", {}).get(
                        row["channel"], []
                    ),
                ]
                if row["asset_id"] == selected_asset and any(
                    re.search(r"\b" + re.escape(alias) + r"\b", lowered)
                    for alias in aliases
                ):
                    present.append(row)
        if present:
            checks.append(
                {
                    "kind": "measurement_availability",
                    "claim": {
                        "category": "unknown",
                        "text": text,
                        "source_ids": sorted({row["evidence_id"] for row in present}),
                    },
                    "status": "contradicted",
                    "reason": "Good-quality source rows exist for the named asset/channel; adequacy for the proposed diagnostic test is not established.",
                }
            )
            corrected.append(
                "Available source readings: "
                + "; ".join(
                    f"{row['asset_id']} / {row['channel']} ({row['unit']}, {row['good_count']} good rows) [{row['evidence_id']}]"
                    for row in present
                )
                + ". The model's absence claim was contradicted; diagnostic sufficiency remains unverified."
            )
        else:
            checks.append(
                {
                    "kind": "measurement_availability",
                    "claim": {"category": "unknown", "text": text, "source_ids": []},
                    "status": "unverified",
                    "reason": "No deterministic absence/adequacy conclusion is established by this text.",
                }
            )
            corrected.append(text)
    return corrected, checks
