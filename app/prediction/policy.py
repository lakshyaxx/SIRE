"""Reversible production selection policy over the unchanged complete research catalog."""

import yaml
from app.core.config import ROOT
from app.core.errors import SireError
from app.prediction.hub import catalog

POLICY = yaml.safe_load((ROOT / "config/prediction.yaml").read_text(encoding="utf-8"))


def selections(rows: list[dict] | None = None) -> dict[str, dict[str, str]]:
    """Choose ready saved pathways by declared family/seed, never by holdout metrics."""
    rows = catalog() if rows is None else rows
    result = {}
    for dataset in sorted({row["dataset"] for row in rows}):
        result[dataset] = {}
        for role, family in POLICY["primary_families"].items():
            candidates = [
                row
                for row in rows
                if row["dataset"] == dataset
                and row["family"] == family
                and row["task"] == "rul"
                and row["status"] == "ready"
            ]
            if candidates:
                chosen = min(
                    candidates,
                    key=lambda row: (
                        not row["default"],
                        row["seed"] != POLICY["preferred_seed"],
                        row["seed"],
                        row["model_id"],
                    ),
                )
                result[dataset][role] = chosen["model_id"]
    return result


def models() -> list[dict]:
    """Annotate copies for UI/routing; trained artifacts, original defaults and research routes remain intact."""
    rows = catalog()
    selected = selections(rows)
    return [
        {
            **row,
            "catalog_default": row["default"],
            "default": row["model_id"] == selected[row["dataset"]].get("low_latency"),
            "production_role": next(
                (
                    role
                    for role, identifier in selected[row["dataset"]].items()
                    if identifier == row["model_id"]
                ),
                "research_available",
            ),
        }
        for row in rows
    ]


def default_model(dataset: str) -> dict:
    """Resolve a valid saved LightGBM source; never substitute another dataset/model family."""
    for row in models():
        if row["dataset"] == dataset and row["default"]:
            return row
    raise SireError(
        "production_pathway_unavailable",
        "No verified low-latency LightGBM route is available for this dataset.",
        503,
    )
