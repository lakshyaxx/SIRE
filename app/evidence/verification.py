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
from app.core.config import SETTINGS

ClaimKind = Literal[
    "direct_observation",
    "reported_observation",
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
        Literal[
            "baseline_mean",
            "recent_mean",
            "delta",
            "percent_delta",
            "count",
            "rul_cycles",
        ]
        | None
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
    if claim.category == "reported_observation":
        for record in records:
            if record["source_type"] == "model_generated":
                continue
            observation = record["observation"]
            quoted = next(
                (
                    observation[key]
                    for key in ("claim", "text", "excerpt", "observation")
                    if isinstance(observation.get(key), str)
                ),
                "",
            )
            for value, unit, context in reported_quantities(quoted):
                if claim.value == value and canonical_unit(
                    claim.unit
                ) == canonical_unit(unit):
                    if claim.observed_at is not None and utc(
                        claim.observed_at.isoformat()
                    ) not in {utc(s) for s in STAMP.findall(context)}:
                        continue
                    if claim.statistic is not None:
                        words = {
                            "baseline_mean": r"\bbaseline\b",
                            "recent_mean": r"\b(?:mean|average|recent)\b",
                            "delta": r"\b(?:delta|change)\b",
                            "percent_delta": r"\b(?:increas\w*|decreas\w*|dropp?\w*|change|delta|reduc\w*)\b",
                        }
                        if claim.statistic not in words or not re.search(
                            words[claim.statistic], context, re.I
                        ):
                            continue
                    return result(
                        "supported_contextually",
                        "Exact quantity and unit in a supplied report; not an independently measured value or verified causal inference",
                        value,
                    )
        return result(
            "insufficient_evidence",
            "The claimed quantity/unit/time is not stated in the cited report; no measurement or calculation is invented",
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
                            "excerpt",
                            record["observation"].get(
                                "observation", record["observation"].get("claim", "")
                            ),
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
    unit_mismatch = False
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
        percent_delta = (
            claim.category == "derived_statistic" and claim.statistic == "percent_delta"
        )
        if claim.unit is None or (
            canonical_unit(claim.unit) != canonical_unit(unit)
            and not (percent_delta and claim.unit in {"%", "percent"})
        ):
            unit_mismatch = True
            continue
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
            if not baseline or not recent:
                continue
            window = (
                baseline
                if claim.statistic == "baseline_mean"
                else (
                    recent
                    if claim.statistic == "recent_mean"
                    else (
                        rows
                        if claim.statistic == "count"
                        else [baseline[0], recent[-1]]
                    )
                )
            )
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
            if statistics["baseline_mean"] != 0:
                statistics["percent_delta"] = (
                    statistics["delta"] / statistics["baseline_mean"] * 100
                )
            if claim.statistic in statistics:
                values.append(float(statistics[claim.statistic]))
    if not values:
        if unit_mismatch:
            return result(
                "contradicted",
                "Claim unit does not match the cited quantity; no implicit conversion",
            )
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


UNIT_ALIASES = {
    alias: unit
    for unit, aliases in SETTINGS["numeric_unit_aliases"].items()
    for alias in aliases
}
NUMBER_UNIT = re.compile(
    r"(?<![\w.])(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*("
    + "|".join(
        re.escape(alias) for alias in sorted(UNIT_ALIASES, key=len, reverse=True)
    )
    + r")(?=$|[\s.,;:)\]])"
)
SOURCE = re.compile(
    r"\[((?:EV:[a-fA-F0-9]{64})|(?:[a-fA-F0-9]{24,32}(?::schema)?)|(?:user:[a-fA-F0-9]{32}))\]"
)
STAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})"
)


def canonical_unit(unit: str | None) -> str | None:
    """Normalize only configured notation aliases; never perform an implicit scale conversion."""
    return UNIT_ALIASES.get(unit, unit)


def quantity_mentions(text: str) -> list[tuple[float, str, int]]:
    """Retain both endpoints of a reported range instead of checking only its last value."""
    result = []
    for match in NUMBER_UNIT.finditer(text):
        prefix = text[: match.start()]
        first = re.search(
            r"(-?\d+(?:\.\d+)?)\s*(?:\bto\b|\bthrough\b|[–—-])\s*$", prefix, re.I
        )
        if first:
            result.append((float(first[1]), match[2], first.start(1)))
        result.append((float(match[1]), match[2], match.start(1)))
    return result


def quantity_scope(text: str, offset: int) -> str:
    """Bind a quantity to its comma/semicolon clause before assigning a timestamp."""
    before = max(text.rfind(",", 0, offset), text.rfind(";", 0, offset)) + 1
    after = min(
        (
            value
            for value in (text.find(",", offset), text.find(";", offset))
            if value >= 0
        ),
        default=len(text),
    )
    return text[before:after]


def reported_quantities(text: str) -> list[tuple[float, str, str]]:
    """Read explicitly stated report quantities, retaining range endpoints and source clauses."""
    result = []
    for line in text.splitlines():
        for value, unit, offset in quantity_mentions(line):
            prefix = line[max(0, offset - 65) : offset]
            if re.search(r"\b(?:not|never|no reading of)\s*$", prefix, re.I):
                continue
            scope = quantity_scope(line, offset)
            if not STAMP.search(scope) and len(STAMP.findall(line)) == 1:
                scope = line
            result.append((value, unit, scope))
    return result


class NumericVerificationError(SireError):
    """Retain exact rejected claims for local traces without exposing private filesystem paths."""

    def __init__(self, diagnostics: list[dict]) -> None:
        super().__init__(
            "unsupported_numeric_claim",
            "Model commentary introduced a quantity that cannot be verified with its cited unit, timestamp and aggregation. Commentary withheld; inspect the actual tool facts and sources.",
            503,
        )
        self.diagnostics = diagnostics


def numeric_checks(text: str, ledger: Ledger) -> list[dict]:
    """Classify every recognized quantity against its actual sources without failing the batch."""
    verified = []
    for line in text.splitlines():
        identifiers = SOURCE.findall(line)
        for claimed_value, unit, offset in quantity_mentions(line):
            stamps = STAMP.findall(quantity_scope(line, offset))
            if not stamps and len(STAMP.findall(line)) == 1:
                stamps = STAMP.findall(line)
            stamp = stamps[0] if len(stamps) == 1 else None
            if not math.isfinite(claimed_value):
                verified.append(
                    Verification(
                        claim=Claim(
                            category="unknown",
                            source_ids=identifiers[:8],
                            text=line[:1600],
                            unit=unit,
                        ),
                        status="contradicted",
                        reason="Generated quantity is non-finite; no supported finite measurement was supplied",
                    ).model_dump(mode="json")
                )
                continue
            prefix = line[max(0, offset - 60) : offset].lower()
            labels = re.findall(r"\b(baseline|recent|mean|average|delta)\b", prefix)
            label = labels[-1] if labels else None
            statistic = (
                "percent_delta"
                if unit in {"%", "percent"}
                and re.search(
                    r"\b(?:increas\w*|decreas\w*|dropp?\w*|fell|fall\w*|rose|reduc\w*|declin\w*|change|delta)\b",
                    prefix,
                )
                else (
                    "baseline_mean"
                    if label == "baseline"
                    or (
                        label in {"mean", "average"}
                        and re.search(r"\bbaseline\s+(?:mean|average)\s*$", prefix)
                    )
                    else (
                        "delta"
                        if label == "delta"
                        else (
                            "recent_mean"
                            if label in {"mean", "average", "recent"}
                            else None
                        )
                    )
                )
            )
            if (
                statistic == "percent_delta"
                and claimed_value > 0
                and re.search(
                    r"\b(?:decreas\w*|dropp?\w*|fell|fall\w*|reduc\w*|declin\w*)\b",
                    prefix,
                )
            ):
                claimed_value = -claimed_value
            report_only = False
            if identifiers:
                try:
                    records = [
                        ledger.resolve(identifier)["evidence"]
                        for identifier in identifiers[:8]
                    ]
                    report_only = all(
                        not record["observation"].get("rows")
                        and record["source_type"] != "model_generated"
                        for record in records
                    )
                except SireError:
                    report_only = False
            claim = Claim(
                category=(
                    "reported_observation"
                    if report_only
                    else "derived_statistic" if statistic else "direct_observation"
                ),
                source_ids=identifiers[:8],
                text=line[:1600],
                value=claimed_value,
                unit=unit,
                statistic=statistic,
                window_end=stamp if stamp and statistic else None,
                observed_at=stamp if stamp and not statistic else None,
            )
            checked = verify_claim(claim, ledger)
            verified.append(checked.model_dump(mode="json"))
    return verified


def screen_numeric_prose(text: str, ledger: Ledger) -> list[dict]:
    """Strict compatibility boundary: reject unsupported quantities and preserve diagnostic claims."""
    checks = numeric_checks(text, ledger)
    if any(
        row["status"] not in {"verified_exact", "supported_contextually"}
        for row in checks
    ):
        raise NumericVerificationError(checks)
    return checks


def review_numeric_prose(text: str, ledger: Ledger) -> dict:
    """Withhold only unsupported paragraphs; never publish part of a rejected assertion."""
    accepted, rejected, checks = [], [], []
    for paragraph in re.split(r"\n\s*\n", text):
        values = numeric_checks(paragraph, ledger)
        checks.extend(values)
        bad = [
            row
            for row in values
            if row["status"] not in {"verified_exact", "supported_contextually"}
        ]
        if bad:
            rejected.append({"text": paragraph, "verifications": bad})
        else:
            accepted.append(paragraph)
    return {"text": "\n\n".join(accepted), "rejected": rejected, "checks": checks}


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
