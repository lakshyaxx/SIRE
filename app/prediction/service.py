"""Independent prediction domain: explicit source identity, saved native outputs and provenance."""

from typing import Any
from threading import Event
import time
from app.core.errors import SireError
from app.prediction.datasets import history as uploaded_history
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
    unit_id: int | None = None,
) -> dict[str, Any]:
    """Run one matching saved model; ordinary chat never supplies a hidden default source."""
    if bool(asset_id) == bool(attachment_id):
        raise SireError(
            "invalid_source",
            "Choose exactly one demonstration asset or compatible CSV attachment.",
        )
    started = time.monotonic()
    frame = (
        telemetry.asset_history(asset_id, dataset)
        if asset_id
        else uploaded_history(store, attachment_id, dataset, unit_id)
    )
    if asset_id and unit_id is not None and int(frame.unit.iloc[0]) != unit_id:
        raise SireError(
            "engine_mismatch", "Engine selection differs from the demonstration asset."
        )
    selected = hub.entry(model_id)
    availability = next(row for row in hub.catalog() if row["model_id"] == model_id)
    if availability["status"] in {
        "artifact_missing",
        "preprocessing_missing",
        "dependency_unavailable",
        "loading_failed",
    }:
        raise SireError(
            availability["status"],
            "Saved prediction pathway is unavailable: "
            + str(availability.get("error_details")),
            503,
        )
    output = hub.predict(
        model_id,
        dataset,
        frame,
        task,
        **({"cancel_event": cancel_event} if cancel_event is not None else {}),
    )
    warnings = list(output.get("warnings", []))
    if availability.get("local_parity") == "failed":
        warnings.append(
            "Inference executed on this laptop, but strict historical-reference parity failed: "
            + str(availability.get("error_details"))
        )
    result = {
        "status": "complete",
        "units": "operating_cycles" if task == "rul" else "anomaly_score",
        "source_type": "model_generated",
        "input_source_type": "nasa_simulation" if asset_id else "real_uploaded",
        "dataset": dataset,
        "model_id": model_id,
        "architecture": selected["family"],
        "unit_id": int(frame.unit.iloc[0]),
        "observation_count": len(frame),
        "duration_seconds": time.monotonic() - started,
        "input_sha256": (
            store.attachment(attachment_id)["sha256"] if attachment_id else None
        ),
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
        "warnings": warnings,
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
