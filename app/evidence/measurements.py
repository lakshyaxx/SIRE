"""Explicit tall-format industrial measurements, separate from NASA predictor schemas."""

from collections import defaultdict
import csv
import io
import json
import math
from pathlib import Path
from statistics import mean
from app.core.config import SETTINGS
from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.simulation.repository import utc
from app.storage.database import Store

REQUIRED = {"asset_id", "timestamp", "channel", "value", "unit"}


def expand_wide(rows: list[dict]) -> list[dict] | None:
    """Normalize only the configured explicit header/unit contract, retaining original row/field IDs."""
    if not rows or not {"asset_id", "timestamp_utc"}.issubset(rows[0]):
        return None
    fields = SETTINGS.get("measurement_wide_fields", {})
    selected = [name for name in rows[0] if name in fields]
    if not selected:
        return None
    expanded = []
    for number, row in enumerate(rows, 1):
        if not {"asset_id", "timestamp_utc"}.issubset(row):
            raise ValueError("Missing wide identity/time field")
        for field in selected:
            value = row.get(field)
            if value is None or value == "":
                continue  # Missing channels remain missing; no imputation.
            expanded.append(
                {
                    "asset_id": row["asset_id"],
                    "timestamp": row["timestamp_utc"],
                    "value": value,
                    **fields[field],
                    "source_row": number,
                    "source_field": field,
                    "quality": row.get("quality_flag", "good"),
                    "synthetic": str(row.get("synthetic", False)).casefold() == "true",
                }
            )
    if not expanded:
        raise ValueError("No populated configured measurements")
    return expanded


def parse(content: bytes, suffix: str) -> list[dict] | None:
    """Recognize only explicitly associated, timestamped, unit-bearing tall CSV/JSON rows."""
    if suffix not in {".csv", ".json"}:
        return None
    try:
        if suffix == ".csv":
            rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        else:
            raw = json.loads(content.decode("utf-8-sig"))
            rows = raw if isinstance(raw, list) else [raw]
        if not rows or not isinstance(rows[0], dict):
            return None
        if len(rows) > SETTINGS["max_history_rows"]:
            raise ValueError("Row budget")
        if not REQUIRED.issubset(rows[0]):
            rows = expand_wide(rows)
            if rows is None:
                return None
        result, seen, units = [], set(), {}
        for number, row in enumerate(rows, 1):
            if not REQUIRED.issubset(row) or any(row[key] is None for key in REQUIRED):
                raise ValueError("Missing measurement field")
            asset, channel, unit = (
                str(row["asset_id"]).strip(),
                str(row["channel"]).strip(),
                str(row["unit"]).strip(),
            )
            if (
                not asset
                or not channel
                or not unit
                or max(len(asset), len(channel), len(unit)) > 100
            ):
                raise ValueError("Missing asset/channel/unit")
            stamp = utc(str(row["timestamp"]))
            if isinstance(row["value"], bool):
                raise ValueError("Boolean is not a measured numeric value")
            value = float(row["value"])
            if not math.isfinite(value):
                raise ValueError("Non-finite measurement")
            if (
                (unit == "K" and value < 0)
                or (unit in {"degC", "°C"} and value < -273.15)
                or (unit in {"%", "percent"} and not 0 <= value <= 100)
            ):
                raise ValueError("Invalid declared physical range")
            identity = asset, channel, stamp
            if identity in seen or units.setdefault((asset, channel), unit) != unit:
                raise ValueError(
                    "Duplicate sample or mixed units without explicit conversion"
                )
            seen.add(identity)
            result.append(
                {
                    "asset_id": asset,
                    "channel": channel,
                    "observed_at": stamp,
                    "value": value,
                    "unit": unit,
                    "source_row": row.get("source_row", number),
                    "source_field": row.get("source_field", "value"),
                    "quality": str(row.get("quality", "good")).casefold(),
                    "synthetic": row.get("synthetic", False),
                    "association": "user_declared_unverified",
                }
            )
        return result
    except (ValueError, TypeError, KeyError, UnicodeError, csv.Error) as exc:
        raise SireError(
            "invalid_measurements",
            "Industrial rows require asset_id,timestamp,channel,value,unit; timezone-aware times, finite values, consistent units and valid declared ranges.",
            422,
        ) from exc


def profile(store: Store, conversation_id: str, attachment_id: str) -> dict:
    """Compute real descriptive groups with exact source row snapshots, without NASA inference."""
    item = store.attachment(attachment_id, conversation_id)
    rows = parse(Path(item["path"]).read_bytes(), Path(item["name"]).suffix.lower())
    if rows is None:
        raise SireError(
            "measurement_schema_required",
            "This file has no supported explicit industrial measurement schema; its generic text/CSV remains available.",
            422,
        )
    groups = defaultdict(list)
    for row in rows:
        groups[(row["asset_id"], row["channel"], row["unit"])].append(row)
    summaries = []
    ledger = Ledger(store)
    for (asset, channel, unit), samples in sorted(groups.items()):
        samples.sort(key=lambda row: (row["observed_at"], row["source_row"]))
        baseline = [
            row for row in samples[: min(24, len(samples))] if row["quality"] == "good"
        ]
        recent = [
            row for row in samples[-min(6, len(samples)) :] if row["quality"] == "good"
        ]
        if not baseline or not recent:
            raise SireError(
                "insufficient_measurements",
                "No good-quality measurements in the requested baseline/recent windows.",
                422,
            )
        before, after = mean(row["value"] for row in baseline), mean(
            row["value"] for row in recent
        )
        delta = after - before
        statistics = {
            "count": len(samples),
            "baseline_mean": before,
            "recent_mean": after,
            "delta": delta if math.isfinite(delta) else None,
            "baseline_count": len(baseline),
            "recent_count": len(recent),
        }
        record = ledger.add(
            "real_uploaded",
            item["name"],
            {
                "statistics": statistics,
                "rows": samples,
                "association": "user_declared_unverified",
            },
            {
                "attachment_id": attachment_id,
                "asset_id": asset,
                "channel": channel,
                "source_rows": [row["source_row"] for row in samples],
            },
            content_sha256=item["sha256"],
            available_at=item["created_at"],
            unit=unit,
            asset_id=asset,
            method="uploaded_descriptive_first24_recent6_v1",
            quality="user_supplied_units_and_association_unverified",
        )
        summaries.append(
            {
                "asset_id": asset,
                "channel": channel,
                "unit": unit,
                **statistics,
                "evidence_id": record.id,
                "series": samples[-300:],
                "baseline_window": {
                    "start": baseline[0]["observed_at"],
                    "end": baseline[-1]["observed_at"],
                },
                "recent_window": {
                    "start": recent[0]["observed_at"],
                    "end": recent[-1]["observed_at"],
                },
                "series_scope": "Last300 source readings at most; exact full snapshot remains available by evidence ID.",
            }
        )
    return {
        "groups": summaries,
        "evidence_ids": [row["evidence_id"] for row in summaries],
        "source_type": "real_uploaded",
        "synthetic_declared": any(row.get("synthetic") for row in rows),
        "limitations": [
            "Asset identity, units and timestamps are supplied by the uploader and remain unverified.",
            "Descriptive changes are not a calibrated physical anomaly/fault diagnosis or a NASA RUL estimate.",
            "No implicit unit conversion, trained model transfer, or linkage to the simulated facility is performed.",
        ],
    }


def render_profiles(profiles: list[dict]) -> str:
    """Render actual calculated statistics without asking a language model to repeat arithmetic."""
    lines = [
        "## Uploaded measurement statistics",
        "Uploader-declared units and asset association remain unverified. These are descriptive window statistics, not point measurements, fault confirmation or NASA RUL.",
        "| Asset / channel | Baseline mean | Recent mean | Unit / count | Source |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for profile in profiles:
        if profile.get("synthetic_declared"):
            lines.insert(
                2, "The uploaded rows explicitly declare synthetic measurements."
            )
        for group in profile["groups"]:

            def safe(value: object) -> str:
                return str(value).replace("|", "\\|").replace("\n", " ")

            lines.append(
                f"| {safe(group['asset_id'])} / {safe(group['channel'])} | {group['baseline_mean']:.8g} | {group['recent_mean']:.8g} | {safe(group['unit'])} / {group['count']} | [{group['evidence_id']}] |"
            )
    return (
        "\n\n".join(lines[:2])
        + "\n\n"
        + "\n".join(lines[2:])
        + "\n\nExact window timestamps and original row IDs are available in the source inspector.\n\n"
    )
