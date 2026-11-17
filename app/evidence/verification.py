"""Deterministic source agreement and conservative screening; never an oracle for physical cause."""

from datetime import datetime
import math
import re
from statistics import mean
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.simulation.repository import utc

ClaimKind = Literal[
    "direct_observation",
    "derived_statistic",
    "model_estimate",
    "interpretation",
    "confirmed_finding",
    "unknown",
]
VerificationStatus = Literal[
    "verified_exact",
    "supported_contextually",
    "contradicted",
    "insufficient_evidence",
    "unverified",
]


class Claim(BaseModel):
    """Explicit claim semantics prevent a recent-window mean becoming a timestamped sample."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    category: ClaimKind
    source_ids: list[str] = Field(default_factory=list, max_length=8)
    text: str = Field(default="", max_length=1600)
    value: float | None = None
    unit: str | None = None
    observed_at: datetime | None = None
    as_of: datetime | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    statistic: (
        Literal["baseline_mean", "recent_mean", "delta", "count", "rul_cycles"] | None
    ) = None
    asset_id: str | None = None
    channel: str | None = None

    @field_validator("observed_at", "as_of", "window_start", "window_end")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        """Reject ambiguous local times instead of silently assuming UTC."""
        if value is not None and value.utcoffset() is None:
            raise ValueError("Timezone-aware timestamp required")
        return value


class Verification(BaseModel):
    """Agreement with an uploaded/simulated source does not authenticate the physical measurement."""

    claim: Claim
    status: VerificationStatus
    reason: str
    source_value: float | None = None
    scope: str = (
        "Source agreement only; source authenticity, physical cause and calibrated confidence remain unverified."
    )


def verify_claim(claim: Claim, ledger: Ledger) -> Verification:
    """Check exact value/unit/time/window semantics or retain an explicit unresolved classification."""

    def result(
        status: VerificationStatus, reason: str, value: float | None = None
    ) -> Verification:
        return Verification(
            claim=claim, status=status, reason=reason, source_value=value
        )

    if not claim.source_ids:
        return result("insufficient_evidence", "No source was supplied")
    records = []
    for identifier in claim.source_ids:
        try:
            records.append(ledger.resolve(identifier)["evidence"])
        except SireError:
            return result(
                "insufficient_evidence",
                "A source is unavailable or failed its integrity check",
            )
    if claim.as_of is not None and any(
        utc(record["available_at"]) > utc(claim.as_of.isoformat()) for record in records
    ):
        return result(
            "insufficient_evidence",
            "Evidence was unavailable at the historical cutoff; no future value disclosed",
        )
    if claim.category in {"interpretation", "unknown"}:
        return result(
            "unverified", "A cited source alone does not verify an interpretation"
        )
    if claim.category == "confirmed_finding":
        return result(
            "insufficient_evidence",
            "Independent physical confirmation criteria have not been established",
        )
    if claim.value is None:
        quote = claim.text.strip().strip('"“”')
        if quote and all(
            record["source_type"] != "model_generated" for record in records
        ):

            def normalize(value: object) -> str:
                return " ".join(str(value).split())

            if any(
                normalize(quote)
                in normalize(
                    record["observation"].get(
                        "text",
                        record["observation"].get(
                            "excerpt", record["observation"].get("observation", "")
                        ),
                    )
                )
                for record in records
            ):
                return result(
                    "supported_contextually",
                    "Exact document statement only; not proof that it applies to this asset",
                )
        return result(
            "unverified",
            "No deterministic numeric or exact quoted claim can be checked",
        )
    values = []
    for record in records:
        observation = record["observation"]
        if claim.category == "model_estimate":
            if (
                record["extraction_method"]
                in {
                    "preserved_native_predictor",
                    "v2_prediction_compatibility_snapshot",
                }
                and claim.statistic == "rul_cycles"
                and claim.unit == "operating_cycles"
            ):
                if observation.get("rul_cycles") is not None:
                    values.append(float(observation["rul_cycles"]))
            continue
        if record["source_type"] == "model_generated":
            continue
        rows = observation.get("rows", [])
        rows = [
            row
            for row in rows
            if (claim.asset_id is None or row.get("asset_id") == claim.asset_id)
            and (
                claim.channel is None
                or row.get("channel", record["pointer"].get("channel")) == claim.channel
            )
        ]
        if not rows:
            continue
        unit = (
            "count"
            if claim.category == "derived_statistic" and claim.statistic == "count"
            else record.get("unit") or rows[0].get("unit")
        )
        if claim.unit is None or claim.unit != unit:
            return result(
                "contradicted",
                "Claim unit does not match the cited quantity; no implicit conversion",
            )
        if claim.as_of is not None:
            cutoff = utc(claim.as_of.isoformat())
            rows = [
                row
                for row in rows
                if utc(row["observed_at"]) <= cutoff
                and utc(row.get("available_at", record["available_at"])) <= cutoff
            ]
        if claim.category == "direct_observation":
            if claim.observed_at is None:
                return result(
                    "insufficient_evidence",
                    "A point observation needs an explicit timestamp",
                )
            rows = [
                row
                for row in rows
                if utc(row["observed_at"]) == utc(claim.observed_at.isoformat())
                and row.get("quality", "good") == "good"
            ]
            values.extend(
                float(row["value"]) for row in rows if row.get("value") is not None
            )
        elif claim.category == "derived_statistic":
            if claim.observed_at is not None:
                return result(
                    "contradicted",
                    "A window statistic cannot be asserted as a point observation",
                )
            rows = sorted(rows, key=lambda row: row["observed_at"])
            if not rows:
                continue
            baseline = [
                row
                for row in rows[:24]
                if row.get("quality", "good") == "good" and row.get("value") is not None
            ]
            recent = [
                row
                for row in rows[-6:]
                if row.get("quality", "good") == "good" and row.get("value") is not None
            ]
            window = baseline if claim.statistic == "baseline_mean" else recent
            if not baseline or not recent:
                continue
            if claim.window_start is not None and utc(
                claim.window_start.isoformat()
            ) != utc(window[0]["observed_at"]):
                return result(
                    "contradicted",
                    "Claimed aggregation window starts at a different sample",
                )
            if claim.window_end is not None and utc(
                claim.window_end.isoformat()
            ) != utc(window[-1]["observed_at"]):
                return result(
                    "contradicted",
                    "Claimed aggregation window ends at a different sample",
                )
            statistics = {
                "baseline_mean": mean(float(r["value"]) for r in baseline),
                "recent_mean": mean(float(r["value"]) for r in recent),
                "count": len(rows),
            }
            statistics["delta"] = (
                statistics["recent_mean"] - statistics["baseline_mean"]
            )
            if claim.statistic in statistics:
                values.append(float(statistics[claim.statistic]))
    if not values:
        return result(
            "insufficient_evidence",
            "No compatible measured sample, statistic or actual model estimate was supplied",
        )
    if len(set(values)) != 1:
        return result(
            "insufficient_evidence",
            "Cited records give ambiguous or conflicting quantities; specify asset/channel",
        )
    actual = values[0]
    if not math.isfinite(actual):
        return result("insufficient_evidence", "Source value is not finite")
    return result(
        (
            "verified_exact"
            if math.isclose(claim.value, actual, rel_tol=0, abs_tol=1e-12)
            else "contradicted"
        ),
        "Exact source value/unit/time or recomputed window comparison; not a physical truth certification",
        actual,
    )


NUMBER_UNIT = re.compile(
    r"(?<![\w.])(-?\d+(?:\.\d+)?)\s*(mm/s(?:\s+RMS)?|bar|degC|°C|rpm|m3/h|percent|%|cycles)(?=$|[\s.,;:)\]])"
)
SOURCE = re.compile(r"\[((?:EV:[a-fA-F0-9]{64})|(?:[a-fA-F0-9]{24}))\]")
STAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})"
)


def screen_numeric_prose(text: str, ledger: Ledger) -> list[dict]:
    """Block unsupported specific measured quantities before buffered model prose is displayed."""
    verified = []
    for line in text.splitlines():
        identifiers = SOURCE.findall(line)
        stamp = STAMP.search(line)
        for match in NUMBER_UNIT.finditer(line):
            prefix = line[max(0, match.start() - 60) : match.start()].lower()
            statistic = (
                "baseline_mean"
                if "baseline" in prefix
                else (
                    "delta"
                    if "delta" in prefix
                    else (
                        "recent_mean"
                        if any(word in prefix for word in ["mean", "average", "recent"])
                        else None
                    )
                )
            )
            claim = Claim(
                category="derived_statistic" if statistic else "direct_observation",
                source_ids=identifiers[:8],
                text=line[:1600],
                value=float(match[1]),
                unit=match[2],
                statistic=statistic,
                window_end=stamp[0] if stamp and statistic else None,
                observed_at=stamp[0] if stamp and not statistic else None,
            )
            checked = verify_claim(claim, ledger)
            verified.append(checked.model_dump(mode="json"))
            if checked.status not in {"verified_exact", "supported_contextually"}:
                raise SireError(
                    "unsupported_numeric_claim",
                    "Model commentary introduced a quantity that cannot be verified with its cited unit, timestamp and aggregation. Commentary withheld; inspect the actual tool facts and sources.",
                    503,
                )
    return verified


def verify_profile_claims(profiles: list[dict], ledger: Ledger) -> list[dict]:
    """Independently check rendered group statistics against their immutable full row snapshots."""
    checks = []
    for profile in profiles:
        for group in profile["groups"]:
            for statistic in ["baseline_mean", "recent_mean", "delta", "count"]:
                if group.get(statistic) is None:
                    continue
                window = (
                    group.get(
                        (
                            "baseline_window"
                            if statistic == "baseline_mean"
                            else "recent_window"
                        ),
                        {},
                    )
                    if statistic in {"baseline_mean", "recent_mean"}
                    else {}
                )
                claim = Claim(
                    category="derived_statistic",
                    source_ids=[group["evidence_id"]],
                    text=f"{group['asset_id']} / {group['channel']}: {statistic}",
                    value=group[statistic],
                    unit="count" if statistic == "count" else group["unit"],
                    statistic=statistic,
                    asset_id=group["asset_id"],
                    channel=group["channel"],
                    window_start=window.get("start"),
                    window_end=window.get("end"),
                )
                check = verify_claim(claim, ledger)
                checks.append(check.model_dump(mode="json"))
                if check.status != "verified_exact":
                    raise SireError(
                        "source_numeric_inconsistency",
                        "Calculated statistics did not match their exact source rows; output withheld.",
                        503,
                    )
    return checks
