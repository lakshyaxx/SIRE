"""Focused deterministic percentage-change checks without document-parser fixtures."""

import pytest

from app.core.errors import SireError
from app.evidence.ledger import Ledger
from app.evidence.verification import Claim, screen_numeric_prose, verify_claim


def percentage_source(store) -> tuple[Ledger, str]:
    """Create exact test-only rows with a 1-to-2 recent-window change."""
    ledger = Ledger(store)
    rows = [
        {
            "asset_id": "TEST-ONLY",
            "channel": "pressure",
            "observed_at": f"2026-01-{index + 1:02d}T00:00:00+00:00",
            "value": 1.0 if index < 24 else 2.0,
            "unit": "bar",
            "quality": "good",
        }
        for index in range(30)
    ]
    record = ledger.add(
        "real_uploaded",
        "Test-only percentage rows",
        {"rows": rows},
        {"test_only": True},
        unit="bar",
        available_at=rows[-1]["observed_at"],
        method="uploaded_descriptive_first24_recent6_v1",
    )
    return ledger, record.id


def test_percent_delta_is_recomputed_with_sign_and_source_unit(store):
    ledger, identifier = percentage_source(store)
    claim = Claim(
        category="derived_statistic",
        source_ids=[identifier],
        value=100,
        unit="%",
        statistic="percent_delta",
        asset_id="TEST-ONLY",
        channel="pressure",
        window_start="2026-01-01T00:00:00Z",
        window_end="2026-01-30T00:00:00Z",
    )
    checked = verify_claim(claim, ledger)
    assert checked.status == "verified_exact" and checked.source_value == 100
    wrong_sign = verify_claim(claim.model_copy(update={"value": -100}), ledger)
    assert wrong_sign.status == "contradicted" and wrong_sign.source_value == 100
    wrong_window = verify_claim(
        claim.model_copy(
            update={
                "window_start": Claim(
                    category="unknown", window_start="2026-01-24T00:00:00Z"
                ).window_start
            }
        ),
        ledger,
    )
    assert wrong_window.status == "contradicted"


def test_percent_prose_requires_exact_cited_change(store):
    ledger, identifier = percentage_source(store)
    checks = screen_numeric_prose(
        f"Pressure increased by 100% [{identifier}].",
        ledger,
    )
    assert checks[0]["status"] == "verified_exact"
    with pytest.raises(SireError, match="cannot be verified"):
        screen_numeric_prose(
            f"Pressure decreased by 100% [{identifier}].",
            ledger,
        )
