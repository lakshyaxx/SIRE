"""Verify numerical model narration against actual tool values; never invent confidence levels."""

import re
from app.core.errors import SireError


def facts(result: dict) -> str:
    """Render actual saved inference numbers, with an explicit distinction from measurement."""
    if result.get("rul_cycles") is None:
        anomaly = result.get("anomaly") or {}
        return f"**Experimental anomaly tool:** score {anomaly.get('anomaly_score')}; native threshold {anomaly.get('threshold')}.\n\nNo remaining-life estimate or confidence percentage is supplied by this tool.\n\n"
    lines = [
        f"**Saved model inference:** {result['rul_cycles']} operating cycles.",
        f"Model: `{result['model_id']}`; dataset: {result['dataset']}; source: {result.get('asset_id') or result.get('attachment_id')}.",
    ]
    if result.get("unit_id") is not None:
        lines.append(
            f"Engine/unit: {result['unit_id']}; observations: {result.get('observation_count')}; reference cycle: {result['last_cycle']}."
        )
    if result.get("warnings"):
        lines.extend("Warning: " + warning for warning in result["warnings"])
    if result.get("interval"):
        lines.append(
            f"Native interval endpoints: {result['interval'][0]} to {result['interval'][1]} cycles. Method: `{result['interval_method']}`. This is not an exact confidence percentage about a physical component."
        )
    lines.append(
        "Simulation-domain estimate, not a measured lifespan or certified maintenance limit."
    )
    return "\n\n".join(lines) + "\n\n"


def validate(
    text: str, result: dict, compared_results: list[dict] | None = None
) -> None:
    """Reject unsupported percent/CI language and cycle values inconsistent with native output."""
    if re.search(
        r"\b\d+(?:\.\d+)?\s*(?:%|percent\b)|\bconfidence\s+interval\b", text, re.I
    ):
        raise SireError(
            "unsupported_prediction_claim",
            "Local model introduced unsupported confidence language; its commentary was withheld. Actual tool facts are shown.",
            503,
        )
    if re.search(
        r"\b\d+(?:\.\d+)?\s*(?:days?|weeks?|months?|years?|hours?)\b", text, re.I
    ):
        raise SireError(
            "unsupported_prediction_claim",
            "NASA cycle outputs do not establish a calendar-life or maintenance interval; commentary withheld.",
            503,
        )
    values = [
        float(result["last_cycle"]),
        *[float(v) for v in result.get("interval") or []],
    ]
    if result.get("rul_cycles") is not None:
        values.append(float(result["rul_cycles"]))
    elif re.search(
        r"\b(?:rul|remaining\s+(?:useful\s+)?life)\b.{0,60}\b\d+(?:\.\d+)?\s*cycles?",
        text,
        re.I,
    ):
        raise SireError(
            "unsupported_prediction_claim",
            "An anomaly score cannot supply RUL; commentary withheld.",
            503,
        )
    for compared in compared_results or []:
        values.append(float(compared["last_cycle"]))
        values.extend(float(value) for value in compared.get("interval") or [])
        if compared.get("rul_cycles") is not None:
            values.append(float(compared["rul_cycles"]))
    for match in re.finditer(
        r"\b(\d+(?:\.\d+)?)\s*(?:operating\s+)?cycles?\b", text, re.I
    ):
        written = match.group(1)
        precision = len(written.split(".")[1]) if "." in written else 0
        tolerance = 0.5 * 10 ** (-precision) + 1e-8
        if not any(abs(float(written) - value) <= tolerance for value in values):
            raise SireError(
                "unsupported_prediction_claim",
                "Local model introduced a cycle value absent from the saved result; commentary withheld.",
                503,
            )
    if re.search(
        r"(?<!not )\bmeasured\s+(?:model result|rul|remaining useful life|lifespan)\b",
        text,
        re.I,
    ):
        raise SireError(
            "unsupported_prediction_claim",
            "Predicted life is not a measured physical lifespan; model commentary withheld.",
            503,
        )
