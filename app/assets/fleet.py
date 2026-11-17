"""Unit-aware fleet indicators over selected simulation scope; no invented failure probabilities."""

from app.evidence.ledger import Ledger
from app.simulation.repository import Observations
from app.temporal.analytics import summarize
from app.investigation.facility import rank


def overview(
    repo: Observations,
    ledger: Ledger,
    scenario_id: str,
    as_of: str | None,
    peer_asset_id: str | None = None,
) -> dict:
    """Compute current quality/trend indicators only from records inside the replay fence."""
    cutoff = repo.cutoff(scenario_id, as_of)
    registered = repo.assets(scenario_id)
    peer_type = None
    if peer_asset_id:
        reference = repo.asset(scenario_id, peer_asset_id)
        peer_type = reference.get("asset_type") or reference["id"].partition("-")[0]
        registered = [
            asset
            for asset in registered
            if (asset.get("asset_type") or asset["id"].partition("-")[0]) == peer_type
        ]
    assets = []
    for asset in registered:
        summary = summarize(repo, ledger, scenario_id, asset["id"], cutoff)
        observed = [r for r in summary["channels"].values() if r["available"]]
        ranked = rank([summary], [])
        assets.append(
            {
                "asset_id": asset["id"],
                "asset_type": summary["asset_type"],
                "channels": summary["channels"],
                "latest_observed_at": max(
                    (r["latest_observed_at"] for r in summary["channels"].values()),
                    default=None,
                ),
                "quality": (
                    "missing_or_insufficient"
                    if not observed or len(observed) < len(summary["channels"])
                    else "valid_synthetic"
                ),
                "missing_samples": sum(
                    r["missing_count"] for r in summary["channels"].values()
                ),
                "trend_mechanisms": [h["id"] for h in ranked if h["support"]],
                "evidence_ids": summary["evidence_ids"],
                "rule": "Any listed trend is a candidate indicator; not probability or an equipment command.",
            }
        )
    return {
        "scenario_id": scenario_id,
        "as_of": cutoff,
        "source_type": "sire_synthetic_scenario",
        "assets": assets,
        "comparison_scope": (
            "same_asset_type" if peer_asset_id else "all_registered_assets"
        ),
        "peer_asset_id": peer_asset_id,
        "asset_type": peer_type,
        "evidence_ids": list(
            dict.fromkeys(e for asset in assets for e in asset["evidence_ids"])
        ),
    }
