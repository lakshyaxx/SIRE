"""Independent negative controls: valid citation with false value/time/unit is not support."""

import pytest
from app.evidence.ledger import Ledger
from app.evidence.verification import Claim, verify_claim, screen_numeric_prose
from app.core.errors import SireError
from app.evidence.measurements import profile
import json


def source(store):
    ledger = Ledger(store)
    record = ledger.add(
        "real_uploaded",
        "Explicit test-only measurements",
        {
            "rows": [
                {
                    "asset_id": "TEST-ONLY",
                    "channel": "vibration",
                    "observed_at": "2026-01-01T03:00:00+00:00",
                    "value": 2.685,
                    "unit": "mm/s RMS",
                    "quality": "good",
                },
                {
                    "asset_id": "TEST-ONLY",
                    "channel": "vibration",
                    "observed_at": "2026-01-01T08:00:00+00:00",
                    "value": 4.907,
                    "unit": "mm/s RMS",
                    "quality": "good",
                },
            ]
        },
        {"test_only": True},
        unit="mm/s RMS",
        available_at="2026-01-01T08:00:00+00:00",
        method="uploaded_descriptive_first24_recent6_v1",
    )
    return ledger, record.id


def test_known_mean_to_point_error_is_rejected_despite_valid_source_id(store):
    ledger, identifier = source(store)
    claim = Claim(
        category="direct_observation",
        source_ids=[identifier],
        value=4.907,
        unit="mm/s RMS",
        observed_at="2026-01-01T03:00:00Z",
    )
    result = verify_claim(claim, ledger)
    assert result.status == "contradicted" and result.source_value == 2.685
    assert (
        verify_claim(claim.model_copy(update={"value": 2.685}), ledger).status
        == "verified_exact"
    )
    with pytest.raises(SireError, match="cannot be verified"):
        screen_numeric_prose(
            f"Vibration was 4.907 mm/s RMS at 2026-01-01T03:00:00Z [{identifier}].",
            ledger,
        )
    assert (
        screen_numeric_prose(
            f"Vibration was 2.685 mm/s RMS at 2026-01-01T03:00:00Z [{identifier}].",
            ledger,
        )[0]["status"]
        == "verified_exact"
    )


def test_mean_is_recomputed_and_cannot_be_given_a_point_timestamp(store):
    ledger, identifier = source(store)
    claim = Claim(
        category="derived_statistic",
        source_ids=[identifier],
        value=3.796,
        unit="mm/s RMS",
        statistic="recent_mean",
    )
    assert verify_claim(claim, ledger).status == "verified_exact"
    assert (
        verify_claim(
            claim.model_copy(
                update={
                    "observed_at": Claim(
                        category="unknown", observed_at="2026-01-01T03:00:00Z"
                    ).observed_at
                }
            ),
            ledger,
        ).status
        == "contradicted"
    )
    assert (
        verify_claim(claim.model_copy(update={"unit": "bar"}), ledger).status
        == "contradicted"
    )


def test_future_evidence_is_not_disclosed_and_a_photo_is_not_physical_confirmation(
    store,
):
    ledger, identifier = source(store)
    late = verify_claim(
        Claim(
            category="direct_observation",
            source_ids=[identifier],
            value=2.685,
            unit="mm/s RMS",
            observed_at="2026-01-01T03:00:00Z",
            as_of="2026-01-01T04:00:00Z",
        ),
        ledger,
    )
    assert late.status == "insufficient_evidence" and late.source_value is None
    image = ledger.add(
        "model_generated",
        "Test-only visual interpretation",
        {"observation": "Possible surface coloration"},
        {"test_only": True},
        method="actual_local_vision",
    )
    assert (
        verify_claim(
            Claim(
                category="confirmed_finding",
                source_ids=[image.id],
                text="Confirmed hidden bearing fracture",
            ),
            ledger,
        ).status
        == "insufficient_evidence"
    )
    assert (
        verify_claim(
            Claim(
                category="interpretation",
                source_ids=[image.id],
                text="Possible corrosion",
            ),
            ledger,
        ).status
        == "unverified"
    )


def test_claim_api_enforces_conversation_linkage(v2client):
    cid = v2client.post("/api/v1/conversations", json={}).json()["id"]
    content = b"asset_id,timestamp,channel,value,unit\nTEST-ONLY,2026-01-01T03:00:00Z,vibration,2.685,mm/s RMS\n"
    upload = v2client.post(
        "/api/v1/attachments",
        data={"conversation_id": cid},
        files={"file": ("test-only.csv", content)},
    ).json()
    record = profile(v2client.app.state.store, cid, upload["id"])["evidence_ids"][0]
    claim = {
        "category": "direct_observation",
        "source_ids": [record],
        "value": 2.685,
        "unit": "mm/s RMS",
        "observed_at": "2026-01-01T03:00:00Z",
    }
    checked = v2client.post(
        "/api/v1/evidence/verify", json={"conversation_id": cid, "claims": [claim]}
    )
    assert (
        checked.status_code == 200
        and checked.json()["verifications"][0]["status"] == "verified_exact"
    )
    other = v2client.post("/api/v1/conversations", json={}).json()["id"]
    assert (
        v2client.post(
            "/api/v1/evidence/verify",
            json={"conversation_id": other, "claims": [claim]},
        ).status_code
        == 404
    )


def test_buffered_model_false_point_is_withheld_by_real_chat_path(
    v2client, provider, monkeypatch
):
    cid = v2client.post("/api/v1/conversations", json={}).json()["id"]
    content = b"asset_id,timestamp,channel,value,unit\nTEST-ONLY,2026-01-01T03:00:00Z,vibration,2.685,mm/s RMS\n"
    upload = v2client.post(
        "/api/v1/attachments",
        data={"conversation_id": cid},
        files={"file": ("test-only.csv", content)},
    ).json()
    record = profile(v2client.app.state.store, cid, upload["id"])["evidence_ids"][0]

    async def false_point(*args):
        yield f"Vibration was 4.907 mm/s RMS at 2026-01-01T03:00:00Z [{record}]."

    monkeypatch.setattr(provider, "stream", false_point)
    response = v2client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": cid,
            "content": "Explain this measured point",
            "attachment_ids": [upload["id"]],
        },
    )
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert (
        events[-1]["status"] == "error"
        and events[-1]["metadata"]["error"]["code"] == "unsupported_numeric_claim"
    )
    assert "Vibration was 4.907" not in "".join(
        event.get("text", "") for event in events
    )
