"""Independent prediction domain: explicit source identity, saved native outputs and provenance."""

from typing import Any
from threading import Event
from app.core.errors import SireError
from app.knowledge.ingestion import csv_history
from app.prediction import hub, telemetry
from app.storage.database import Store


def run(
    store: Store,
    dataset: str,
    model_id: str,
    asset_id: str | None = None,
    attachment_id: str | None = None,
    task: str = "rul",
    cancel_event: Event | None = None,
) -> dict[str, Any]:
    """Run one matching saved model; ordinary chat never supplies a hidden default source."""
    if bool(asset_id) == bool(attachment_id):
        raise SireError(
            "invalid_source",
            "Choose exactly one demonstration asset or compatible CSV attachment.",
        )
    frame = (
        telemetry.asset_history(asset_id, dataset)
        if asset_id
        else csv_history(store, attachment_id, dataset)
    )
    output = hub.predict(
        model_id,
        dataset,
        frame,
        task,
        **({"cancel_event": cancel_event} if cancel_event is not None else {}),
    )
    selected = hub.entry(model_id)
    result = {
        "source_type": "model_generated",
        "input_source_type": "nasa_simulation" if asset_id else "real_uploaded",
        "dataset": dataset,
        "model_id": model_id,
        "purpose": selected["purpose"],
        "asset_id": asset_id,
        "attachment_id": attachment_id,
        "data_origin": telemetry.ORIGIN if asset_id else "user_declared_cmapss",
        "last_cycle": int(frame.cycle.max()),
        "legacy_output": output,
        "rul_cycles": output.get("rul"),
        "interval": output.get("interval_80"),
        "interval_method": output.get("uncertainty_method"),
        "anomaly": output if task == "anomaly" else None,
        "provenance": {
            "source": selected["source"],
            "artifact_dir": selected["artifact_dir"],
            "version": output["version"],
            "seed": selected["seed"],
            "runtime": "cpu",
            "bundle_sha256": hub.manifest()["bundle_sha256"],
        },
        "warnings": output.get("warnings", []),
        "target_policy": selected["target_policy"],
        "limitations": [
            "NASA C-MAPSS simulated turbofan data; operating cycles, not calendar time.",
            "A prediction is model inference, not proof of a failed component or a maintenance limit.",
        ],
    }
    if task == "anomaly":
        result["limitations"].append(
            "Experimental anomaly detector; the score is not RUL."
        )
    store.save_result("predictions", result)
    return result
