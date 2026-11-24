"""Prediction-scoped intent and grounded conversation context; no global prompt changes."""

import json
import re

from app.core.errors import SireError
from app.prediction import datasets, policy
from app.prediction.hub import catalog
from app.storage.database import Store

FAMILIES = {
    "lightgbm": "01_lightgbm",
    "lstm": "02_lstm",
    "bilstm": "03_bilstm_attention",
    "cnn1d": "04_cnn1d",
    "transformer": "05_transformer",
    "ensemble": "08_ensemble",
    "cnn-transformer": "07_cnn_transformer",
    "autoencoder": "06_autoencoder",
}


def latest(store: Store, conversation_id: str) -> str | None:
    """Find only this conversation's last persisted prediction reference."""
    for message in reversed(store.messages(conversation_id)):
        if message["role"] == "assistant" and message["metadata"].get("prediction_id"):
            return message["metadata"]["prediction_id"]
        if message["role"] == "assistant" and message["metadata"].get("attachments"):
            for identifier in message["metadata"]["attachments"]:
                if store.attachment(identifier)["kind"] == "csv":
                    return None
    return None


def resolve(
    store: Store,
    conversation_id: str,
    content: str,
    selected: list[dict],
    prediction_id: str | None,
) -> dict | None:
    """Resolve bounded source/model requests, asking rather than guessing missing identities."""
    text = content.lower()
    inspection = bool(
        re.search(
            r"how many.*(?:rows|engines|units|cycles)|inspect.*(?:dataset|file)|compatible.*(?:lstm|nasa|model)",
            text,
        )
    )
    if inspection and not selected:
        candidates = [
            item
            for item in store.attachments(conversation_id)
            if item["metadata"].get("prediction_dataset")
        ]
        if len(candidates) == 1:
            selected = candidates
    if selected and not any(item["kind"] == "csv" for item in selected):
        return None
    domain = bool(
        re.search(
            r"c-?mapss|\bnasa\b|\bfd00[1-4]\b|\brul\b|remaining useful life|trained models|available models",
            text,
        )
    )
    attached = any(
        a["metadata"].get("prediction_dataset")
        or a["metadata"].get("prediction_eligible")
        for a in selected
    )
    execute = bool(
        re.search(r"\b(?:predict|run|execute|estimate|calculate|compare)\b", text)
    )
    domain = (
        domain
        or bool(
            re.search(
                r"models.*(?:trained|available|on this laptop)|sequence length.*lstm",
                text,
            )
        )
        or (
            execute
            and any(
                re.search(r"\b" + re.escape(word) + r"\b", text)
                for word in FAMILIES
                if word != "transformer"
            )
        )
    )
    followup = bool(
        re.search(
            r"(?:which|what|explain|limitations|mean|compare).*(?:model|result|prediction|cycles|rul|engine)|what did.*predict|why.*(?:predictions|results).*differ",
            text,
        )
    )
    previous = latest(store, conversation_id) if not selected else None
    if (
        not domain
        and not attached
        and not prediction_id
        and not (previous and followup)
    ):
        return None
    if (
        re.search(r"\b(?:investigate|diagnose|hypothes|root cause)\b", text)
        and not domain
    ):
        return None
    conceptual = bool(
        re.match(r"(?:what (?:is|are)|how (?:does|do)|define|explain how)\b", text)
    )
    catalog_question = bool(
        re.search(
            r"models.*(?:trained|available|on this laptop)|sequence (?:length|window)",
            text,
        )
    )
    if (
        not selected
        and not execute
        and not prediction_id
        and domain
        and (
            catalog_question
            or (
                conceptual
                and not re.search(
                    r"\b(?:this|that|my|result|prediction|engine)\b", text
                )
            )
        )
    ):
        return {"kind": "knowledge", "text": knowledge(content)}
    if (
        not selected
        and not execute
        and not prediction_id
        and not (previous and followup)
    ):
        return {"kind": "knowledge", "text": knowledge(content)}
    if conceptual and not attached and not prediction_id and not previous:
        return {"kind": "knowledge", "text": knowledge(content)}
    saved_id = prediction_id or previous
    if (
        saved_id
        and not selected
        and (
            not execute
            or not re.search(
                r"\b(?:run|execute|compare|predict|estimate|calculate)\b", text
            )
        )
    ):
        identifiers = [saved_id]
        if not prediction_id:
            for message in reversed(store.messages(conversation_id)):
                if (
                    message["role"] == "assistant"
                    and message["metadata"].get("prediction_id") == saved_id
                ):
                    identifiers = (
                        message["metadata"].get("prediction_ids") or identifiers
                    )
                    break
        return {
            "kind": "followup",
            "prediction_id": saved_id,
            "prediction_ids": identifiers,
        }
    attachments = selected
    saved = store.result("predictions", saved_id) if saved_id and not selected else None
    if not attachments and saved and execute:
        attachments = (
            [store.attachment(saved["attachment_id"])]
            if saved.get("attachment_id")
            else []
        )
    if (
        not attachments
        and not saved
        and re.search(r"\b(?:uploaded|attached|this file|this dataset)\b", text)
    ):
        attachments = [
            a
            for a in store.attachments(conversation_id)
            if a["metadata"].get("prediction_dataset")
        ]
    source = attachments[0] if len(attachments) == 1 else None
    subset_match = re.search(r"\b(fd00[1-4])\b", text)
    subset = (
        subset_match[1].upper()
        if subset_match
        else (source or {}).get("metadata", {}).get("declared_dataset")
        or (saved or {}).get("dataset")
    )
    unit_match = re.search(r"\b(?:engine|unit)\s*#?\s*(\d+)\b", text)
    unit = int(unit_match[1]) if unit_match else (saved or {}).get("unit_id")
    if source and not execute:
        details = source["metadata"]
        if unit is not None and details.get("engines"):
            details = {
                **details,
                "selected_engine": next(
                    (e for e in details["engines"] if e["unit_id"] == unit), None
                ),
            }
        return {
            "kind": "inspect",
            "text": "Verified full-file dataset summary (preview is limited):\n\n"
            + json.dumps(details, indent=2),
        }
    if len(attachments) > 1:
        return {
            "kind": "clarify",
            "text": "Select one NASA dataset attachment for this prediction.",
        }
    if source:
        if not source["metadata"].get("prediction_eligible"):
            return {
                "kind": "clarify",
                "text": "This attachment has not passed NASA prediction validation and compatibility declaration. Use NASA dataset upload and confirm its subset and simulation provenance.",
            }
        try:
            frame = datasets.history(store, source["id"], subset, unit)
            unit = int(frame.unit.iloc[0])
        except SireError as exc:
            return {"kind": "clarify", "text": exc.message}
    if not subset or unit is None:
        return {
            "kind": "clarify",
            "text": "Specify the NASA subset (FD001-FD004) and engine/unit number. For an uploaded file, attach it using NASA dataset upload and confirm its simulation provenance.",
        }
    rows = [
        r
        for r in policy.models()
        if r["dataset"] == subset and r["task"] == "rul" and r["status"] == "ready"
    ]
    ids = re.findall(r"\bfd00[1-4]-[a-z0-9_-]+-s\d+\b", text)
    families = [
        family
        for word, family in FAMILIES.items()
        if re.search(r"\b" + re.escape(word) + r"\b", text)
    ]
    requested = re.search(r"\b(?:use|using|run)\s+(?:the\s+)?([a-z][a-z0-9_-]*)", text)
    if (
        requested
        and requested[1]
        not in {
            "available",
            "a",
            "an",
            "trained",
            "model",
            "prediction",
            "rul",
            "fd001",
            "fd002",
            "fd003",
            "fd004",
        }
        and not ids
        and not families
    ):
        return {
            "kind": "clarify",
            "text": "The requested model name is not registered. Name a saved model ID or an available family; no substitute was executed.",
        }
    if "03_bilstm_attention" in families and "02_lstm" in families:
        families.remove("02_lstm")
    if "07_cnn_transformer" in families and "05_transformer" in families:
        families.remove("05_transformer")
    compare = "compare" in text or len(ids) > 1 or len(families) > 1
    if ids:
        choices = [r for identifier in ids for r in rows if r["model_id"] == identifier]
        if len(choices) != len(ids):
            return {
                "kind": "clarify",
                "text": "Requested model is unavailable or incompatible with this subset. Ask which models are available.",
            }
    elif families:
        choices = []
        for family in families:
            candidates = [r for r in rows if r["family"] == family]
            if not candidates:
                return {
                    "kind": "clarify",
                    "text": f"No available {family} pathway for {subset}. No substitute was executed.",
                }
            choices.append(
                min(
                    candidates,
                    key=lambda r: (not r["default"], r["seed"] != 42, r["seed"]),
                )
            )
    else:
        choices = [policy.default_model(subset)]
        if compare:
            other = next(
                (r for r in rows if r["family"] == "02_lstm" and r["seed"] == 42), None
            )
            if other:
                choices.append(other)
    if compare and saved:
        prior = next(
            (row for row in rows if row["model_id"] == saved["model_id"]), None
        )
        if prior and all(row["model_id"] != prior["model_id"] for row in choices):
            choices.insert(0, prior)
    if compare and len(choices) < 2:
        return {
            "kind": "clarify",
            "text": "Name two compatible model families or model IDs to compare.",
        }
    source_args = (
        {"attachment_id": source["id"], "unit_id": unit}
        if source
        else {
            "asset_id": f"{subset}-ENGINE-{unit:03d}",
            "unit_id": unit,
        }
    )
    return {
        "kind": "compare" if compare else "run",
        "arguments": [
            {"dataset": subset, "model_id": row["model_id"], **source_args}
            for row in choices[:4]
        ],
    }


def knowledge(content: str) -> str:
    """Render bounded actual catalog information and NASA-specific inference semantics."""
    rows = catalog()
    subset = re.search(r"\b(FD00[1-4])\b", content, re.I)
    rows = [r for r in rows if not subset or r["dataset"] == subset[1].upper()]
    info = [
        f"| {row['model_id']} | {row.get('window_length') or 'native'} | {row.get('availability')} |"
        for row in rows
        if row["seed"] == 42 and row["task"] == "rul"
    ]
    explanation = (
        "NASA C-MAPSS is simulated turbofan degradation, with 26 fields: engine/unit, cycle, 3 operating settings and 21 sensors. "
        "There are 4 subsets. FD001: 1 condition/1 fault mode; FD002: 6 conditions/1 fault mode; FD003: 1 condition/2 fault modes; FD004: 6 conditions/2 fault modes. "
        "RUL is estimated remaining operating cycles, not days or a guaranteed failure date. "
        "Saved training preprocessors select sensors and normalize operating conditions. LightGBM uses engineered window features; neural pathways use saved sequence windows. No scaler is fitted to uploaded data. "
        "A preview is not the full file. A matching schema does not prove NASA provenance; declare the subset and select an engine. "
        "The original sequence loaders repeat the first observation to left-pad short nonempty histories and warn explicitly; input is never silently resized by the upload parser.\n\n"
    )
    if re.search(
        r"model|available|trained|lstm|lightgbm|sequence|support", content, re.I
    ):
        explanation += (
            "Current seed-42 RUL catalog (other saved seeds remain in Models):\n\n| Model ID | Saved window | Current availability |\n| --- | --- | --- |\n"
            + "\n".join(info)
        )
    if re.search(r"metric|accuracy|best|rmse|mae|evaluat|performed", content, re.I):
        if not subset:
            explanation += "\n\nSpecify a NASA subset and evaluation protocol before comparing saved metrics; validation-window and test-engine metrics are different experiments."
        else:
            measured = [
                {
                    "model_id": row["model_id"],
                    "source": row.get("historical_metrics_source"),
                    "saved_metrics": row["historical_metrics"].get("metrics", {}),
                }
                for row in rows
                if row["default"]
            ]
            explanation += (
                "\n\nRecorded research-default evaluation, not a new benchmark or proof of real-aircraft accuracy:\n\n"
                + json.dumps(measured, indent=2)
            )
    return explanation


def validate_knowledge(text: str, context: str) -> None:
    """Reject new figures and unknown model IDs in prediction-specific commentary."""
    allowed = set(re.findall(r"\b\d+(?:\.\d+)?\b", context))
    supplied = set(re.findall(r"\b\d+(?:\.\d+)?\b", text))
    identifiers = re.findall(r"\bfd00[1-4]-[a-z0-9_-]+-s\d+\b", text.lower())
    if (
        supplied - allowed
        or any(identifier not in context.lower() for identifier in identifiers)
        or re.search(r"\d\s*%|confidence\s+interval", text, re.I)
    ):
        raise SireError(
            "unsupported_prediction_claim",
            "Prediction explanation introduced unsupported figures or model identity; verified source facts are preserved.",
            503,
        )


def explanation_context(content: str, displayed: str) -> dict:
    """Supply a compact registry recap while the full exact catalog stays displayed."""
    subset = re.search(r"\b(FD00[1-4])\b", content, re.I)
    rows = [
        row for row in catalog() if not subset or row["dataset"] == subset[1].upper()
    ]
    families = {
        family
        for word, family in FAMILIES.items()
        if re.search(r"\b" + re.escape(word) + r"\b", content, re.I)
    }
    focused = [
        {
            key: row.get(key)
            for key in ("model_id", "dataset", "window_length", "availability")
        }
        for row in rows
        if row["family"] in families and row["seed"] == 42 and row["task"] == "rul"
    ]
    return {
        "domain_facts": displayed.split("Current seed-42 RUL catalog")[0],
        "registered_routes": len(rows),
        "architectures": sorted({row["family"] for row in rows}),
        "requested_model_details": focused,
        "instruction_scope": "Full model table has already been displayed. Give only two short recap sentences; do not repeat the catalog or enumerate model IDs.",
    }
