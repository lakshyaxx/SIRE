"""Verified intermediate source facts, independent of slow visual/model interpretation."""

from app.evidence.ledger import Ledger
from app.evidence.measurements import render_profiles
from app.evidence.verification import verify_profile_claims
from app.storage.database import Store


def verified_facts(store: Store, profile: dict) -> tuple[str, list[dict]]:
    """Recompute exact statistics before emitting descriptive facts; never infer physical cause."""
    checks = verify_profile_claims([profile], Ledger(store))
    return render_profiles([profile]), checks
