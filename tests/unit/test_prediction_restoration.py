"""Prediction intake/routing regressions with real NASA inputs and isolated test state."""

import asyncio
from pathlib import Path

import pandas as pd
import pytest

from app.chat.service import ChatService
from app.core.config import TRACK
from app.core.errors import SireError
from app.prediction import datasets, service
from app.prediction.conversation import resolve
from app.prediction.telemetry import dataset_frame


def test_original_nasa_file_full_summary_and_engine_selection(store):
    content = (TRACK / "data/test_FD001.txt").read_bytes()
    item = datasets.ingest(store, None, "test_FD001.txt", content, "FD001", True)
    meta = item["metadata"]
    assert meta["rows"] == len(dataset_frame("FD001")) > 10000
    assert meta["engine_count"] == 100 and len(meta["preview"]) == 5
    assert Path(store.attachment(item["id"])["path"]).read_bytes() == content
    with pytest.raises(SireError, match="Select an engine"):
        datasets.history(store, item["id"], "FD001")
    frame = datasets.history(store, item["id"], "FD001", 5)
    assert frame.unit.unique().tolist() == [5]
    assert len(frame) == meta["engines"][4]["rows"]


@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
def test_canonical_aliases_and_all_numeric_values(history, delimiter):
    aliased = history.rename(
        columns={"unit": "engine_id", "op1": "setting_1", "s2": "sensor_2"}
    )
    result = datasets.parse(
        aliased.to_csv(index=False, sep=delimiter).encode("utf-8-sig"), "nasa.csv"
    )
    pd.testing.assert_frame_equal(
        result, history.reset_index(drop=True), check_dtype=False
    )


@pytest.mark.parametrize(
    "fault",
    ["nan", "infinity", "duplicate", "missing", "unordered", "fractional", "ragged"],
)
def test_invalid_data_refused_without_dropping_rows(history, fault):
    frame = history.copy()
    if fault == "nan":
        frame.loc[0, "s2"] = float("nan")
    elif fault == "infinity":
        frame.loc[0, "s2"] = float("inf")
    elif fault == "duplicate":
        frame.loc[1, "cycle"] = frame.loc[0, "cycle"]
    elif fault == "missing":
        frame = frame.drop(columns="s2")
    elif fault == "unordered":
        frame = frame.iloc[::-1]
    elif fault == "fractional":
        frame.loc[0, "unit"] = 1.5
    content = frame.to_csv(index=False).encode()
    if fault == "ragged":
        content += b"1,2,3\n"
    with pytest.raises(SireError):
        datasets.parse(content, "bad.csv")


def test_arbitrary_industrial_and_rul_label_files_rejected(store):
    for name, content in [
        ("industrial.csv", b"temperature,vibration\n12,3\n"),
        ("RUL_FD001.txt", b"112\n98\n"),
    ]:
        with pytest.raises(SireError):
            datasets.ingest(store, None, name, content, "FD001", True)
    assert not store.rows("SELECT * FROM attachments")


def test_declaration_and_subset_must_match(store, history):
    item = datasets.ingest(
        store, None, "a.csv", history.to_csv(index=False).encode(), "FD001", False
    )
    with pytest.raises(SireError):
        datasets.history(store, item["id"], "FD001", 1)
    item = datasets.ingest(
        store, None, "a.csv", history.to_csv(index=False).encode(), "FD001", True
    )
    with pytest.raises(SireError):
        datasets.history(store, item["id"], "FD002", 1)


def test_prediction_api_txt_upload_and_invalid_engine(v2client):
    response = v2client.post(
        "/api/v1/predictions/upload",
        data={"dataset": "FD001", "compatible_cmapss": "true"},
        files={
            "file": (
                "NASA.txt",
                (TRACK / "data/test_FD001.txt").read_bytes(),
                "text/plain",
            )
        },
    )
    assert response.status_code == 200, response.text
    item = response.json()
    response = v2client.get(
        f"/api/v1/predictions/uploads/{item['id']}/telemetry?dataset=FD001&unit_id=5"
    )
    assert response.status_code == 200 and all(
        row["unit"] == 5 for row in response.json()["records"]
    )
    response = v2client.get(
        f"/api/v1/predictions/uploads/{item['id']}/telemetry?dataset=FD001&unit_id=999"
    )
    assert response.status_code == 422


def test_chat_prediction_selection_and_no_silent_source_fallback(store):
    conversation = store.create_conversation()["id"]
    item = datasets.ingest(
        store,
        conversation,
        "NASA.txt",
        (TRACK / "data/test_FD001.txt").read_bytes(),
        "FD001",
        True,
    )
    route = resolve(
        store, conversation, "Predict RUL using LightGBM engine 5", [item], None
    )
    assert route["arguments"][0]["attachment_id"] == item["id"]
    assert route["arguments"][0]["unit_id"] == 5
    assert route["arguments"][0]["model_id"].startswith("fd001-01_lightgbm-")
    assert (
        resolve(store, conversation, "Predict RUL", [item], None)["kind"] == "clarify"
    )
    assert (
        resolve(store, conversation, "Investigate my overheating motor", [], None)
        is None
    )
    assert (
        resolve(
            store,
            conversation,
            "Run an investigation of this overheating transformer",
            [],
            None,
        )
        is None
    )


def test_prediction_followup_is_conversation_scoped(store, history):
    a, b = store.create_conversation()["id"], store.create_conversation()["id"]
    payload = {
        "dataset": "FD001",
        "unit_id": 1,
        "model_id": "test-only",
        "asset_id": "FD001-ENGINE-001",
    }
    identifier = store.save_result("predictions", payload)
    store.add_message(
        a,
        "assistant",
        "Test-only saved reference",
        metadata={"prediction_id": identifier},
    )
    assert (
        resolve(store, a, "Which model generated that result?", [], None)[
            "prediction_id"
        ]
        == identifier
    )
    other = resolve(store, b, "Which model generated that result?", [], None)
    assert other is None
    assert resolve(store, a, "What is NASA C-MAPSS?", [], None)["kind"] == "knowledge"
    assert (
        resolve(store, a, "Which models are available for FD004?", [], None)["kind"]
        == "knowledge"
    )
    second = store.save_result(
        "predictions", dict(payload, model_id="test-only-second-model")
    )
    store.add_message(
        a,
        "assistant",
        "Test-only comparison references",
        metadata={"prediction_id": second, "prediction_ids": [identifier, second]},
    )
    route = resolve(store, a, "Why are the two predictions different?", [], None)
    assert route["prediction_ids"] == [identifier, second]
    from app.knowledge.ingestion import ingest
    from app.prediction.conversation import latest

    generic = ingest(
        store, a, "test-only-new-industrial.csv", b"temperature,vibration\n42,0.1\n"
    )
    store.add_message(
        a,
        "assistant",
        "Test-only new incompatible dataset refusal",
        metadata={"attachments": [generic["id"]]},
    )
    assert latest(store, a) is None


def test_real_prediction_upload_and_chat_agree_even_when_explanation_fails(
    store, history, provider
):
    conversation = store.create_conversation()["id"]
    item = datasets.ingest(
        store,
        conversation,
        "nasa.csv",
        history.to_csv(index=False).encode(),
        "FD001",
        True,
    )
    direct = service.run(
        store, "FD001", "fd001-01_lightgbm-s42", attachment_id=item["id"], unit_id=1
    )

    async def fail(*args):
        raise SireError("test_only_outage", "Test-only unavailable explanation", 503)
        yield

    provider.stream = fail

    async def run():
        return [
            event
            async for event in ChatService(store, provider).events(
                conversation,
                "prediction-test",
                "Predict RUL using fd001-01_lightgbm-s42 engine 1",
                [item["id"]],
                "chat",
                None,
                None,
                False,
            )
        ]

    events = asyncio.run(run())
    final = events[-1]
    assert final["status"] == "partial"
    actual = store.result("predictions", final["metadata"]["prediction_id"])
    assert actual["rul_cycles"] == pytest.approx(direct["rul_cycles"], abs=1e-8)
    assert final["metadata"]["prediction_status"] == "complete"
    assert str(actual["rul_cycles"]) in store.messages(conversation)[-1]["content"]


def test_input_integrity_and_short_sequence_gate(store, history):
    item = datasets.ingest(
        store,
        None,
        "short.csv",
        history.head(2).to_csv(index=False).encode(),
        "FD001",
        True,
    )
    result = service.run(
        store, "FD001", "fd001-01_lightgbm-s42", attachment_id=item["id"], unit_id=1
    )
    assert result["observation_count"] == 2
    assert any("left-padded" in warning for warning in result["warnings"])
    Path(store.attachment(item["id"])["path"]).write_bytes(b"changed test fixture")
    with pytest.raises(SireError, match="bytes changed"):
        datasets.history(store, item["id"], "FD001", 1)


def test_inspection_does_not_confuse_preview_with_file(store):
    conversation = store.create_conversation()["id"]
    datasets.ingest(
        store,
        conversation,
        "test_FD001.txt",
        (TRACK / "data/test_FD001.txt").read_bytes(),
        "FD001",
        True,
    )
    route = resolve(
        store, conversation, "How many engines and rows are present?", [], None
    )
    assert route["kind"] == "inspect" and '"rows": 13096' in route["text"]
    assert '"engine_count": 100' in route["text"]
    assert not store.rows("SELECT * FROM predictions")


def test_new_dataset_does_not_inherit_old_unit_or_model(store, history):
    conversation = store.create_conversation()["id"]
    old = {
        "dataset": "FD001",
        "unit_id": 5,
        "model_id": "test-only",
        "asset_id": "FD001-ENGINE-005",
    }
    identifier = store.save_result("predictions", old)
    store.add_message(
        conversation,
        "assistant",
        "Test-only old result",
        metadata={"prediction_id": identifier},
    )
    item = datasets.ingest(
        store,
        conversation,
        "new.txt",
        (TRACK / "data/test_FD001.txt").read_bytes(),
        "FD001",
        True,
    )
    route = resolve(store, conversation, "Predict RUL", [item], identifier)
    assert route["kind"] == "clarify" and "Select an engine" in route["text"]


def test_unknown_explicit_model_is_not_replaced(store):
    conversation = store.create_conversation()["id"]
    route = resolve(
        store, conversation, "Predict FD001 engine 1 using xgboost", [], None
    )
    assert route["kind"] == "clarify" and "not registered" in route["text"]


def test_missing_weight_is_not_exposed_as_ready(monkeypatch):
    from app.prediction import hub

    original = hub.manifest()
    item = dict(
        original["models"][0],
        weight_paths=["ml/artifacts/cmapss/not-a-real-test-weight.pt"],
    )
    monkeypatch.setattr(hub, "manifest", lambda: {**original, "models": [item]})
    row = hub.catalog()[0]
    assert row["status"] == "artifact_missing"
    assert row["error_details"]["missing_paths"] == [
        "ml/artifacts/cmapss/not-a-real-test-weight.pt"
    ]


def test_knowledge_commentary_cannot_invent_metrics():
    from app.prediction.conversation import validate_knowledge

    with pytest.raises(SireError):
        validate_knowledge("The model is 99% accurate", "NASA C-MAPSS has 21 sensors.")


def test_photo_attachment_cannot_select_unrelated_demo_history():
    from app.orchestration.runtime import chat_plan

    plan = chat_plan(
        "Predict RUL of photo using FD001 engine 1", ["image"], False, None
    )
    assert not any(invocation.tool_id == "prediction.run" for invocation in plan.tools)


def test_comparison_narration_accepts_only_values_from_actual_results():
    from app.prediction.narrative import validate

    first = {"rul_cycles": 12.5, "last_cycle": 31, "interval": None}
    second = {"rul_cycles": 19.25, "last_cycle": 31, "interval": None}
    validate(
        "First model estimated 12.5 cycles; second estimated 19.25 cycles.",
        first,
        [second],
    )
    with pytest.raises(SireError):
        validate("Another model estimated 99 cycles.", first, [second])
    with pytest.raises(SireError):
        validate("Confidence interval with 95% confidence.", first, [second])


def test_handed_off_comparison_keeps_original_uploaded_source(store, history):
    conversation = store.create_conversation()["id"]
    item = datasets.ingest(
        store,
        None,
        "test-only-nasa.csv",
        history.to_csv(index=False).encode(),
        "FD001",
        True,
    )
    identifier = store.save_result(
        "predictions",
        {
            "dataset": "FD001",
            "unit_id": 1,
            "model_id": "fd001-01_lightgbm-s42",
            "attachment_id": item["id"],
            "asset_id": None,
        },
    )
    route = resolve(
        store,
        conversation,
        "Compare this result with fd001-01_lightgbm-original-s42 on the same engine",
        [],
        identifier,
    )
    assert route["kind"] == "compare" and len(route["arguments"]) == 2
    assert all(
        args["attachment_id"] == item["id"] and args["unit_id"] == 1
        for args in route["arguments"]
    )
    assert not any(args.get("asset_id") for args in route["arguments"])
