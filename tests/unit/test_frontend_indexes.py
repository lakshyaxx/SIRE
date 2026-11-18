"""Presentation indexes read actual temporary records, never production data or model claims."""

import json
from app.core.config import SETTINGS


def test_config_and_attachment_index_are_read_only_and_do_not_expose_paths(v2client):
    client = v2client
    cid = client.post(
        "/api/v1/conversations", json={"title": "Explicit test-only source"}
    ).json()["id"]
    response = client.post(
        "/api/v1/attachments",
        data={"conversation_id": cid},
        files={
            "file": (
                "test-only.txt",
                b"Explicit test-only document.\nSecond source line.",
                "text/plain",
            )
        },
    )
    assert response.status_code == 200
    attachment = response.json()
    store = client.app.state.store
    before = store.rows("SELECT * FROM attachments ORDER BY id")
    config = client.get("/api/v1/frontend/config").json()
    assert config["max_upload_bytes"] == SETTINGS["max_upload_bytes"]
    assert {".pdf", ".docx", ".xlsx", ".wav", ".mp4", ".csv"} <= set(
        config["upload_extensions"]
    )
    page = client.get(
        "/api/v1/frontend/attachments",
        params={"conversation_id": cid, "query": "test-only", "page_size": 1},
    ).json()
    assert page["total"] == 1 and page["items"][0]["id"] == attachment["id"]
    assert "path" not in page["items"][0]
    assert page["items"][0]["size_bytes"] == len(
        b"Explicit test-only document.\nSecond source line."
    )
    assert (
        client.get(
            "/api/v1/frontend/attachments", params={"query": "absent-test-only-name"}
        ).json()["total"]
        == 0
    )
    resolved = client.get("/api/v1/frontend/attachments/" + attachment["id"]).json()
    assert resolved["sha256"] == attachment["sha256"] and "path" not in resolved
    assert (
        client.get("/api/v1/frontend/attachments", params={"page": 0}).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/frontend/attachments",
            params={"conversation_id": "not-a-conversation"},
        ).status_code
        == 404
    )
    assert store.rows("SELECT * FROM attachments ORDER BY id") == before


def test_saved_case_and_job_indexes_preserve_errors_scope_and_deduplicate(v2client):
    client = v2client
    store = client.app.state.store
    first = store.create_conversation("Explicit test-only first conversation")["id"]
    second = store.create_conversation("Explicit test-only second conversation")["id"]
    report = {
        "case": {
            "question": "Explicit test-only saved question",
            "conversation_id": first,
            "evidence": [],
        },
        "hypotheses": [],
        "unresolved": ["Explicit unresolved test-only condition"],
    }
    case_id = store.save_result("cases", report, first)
    user = store.add_message(first, "user", "Explicit test-only job question")
    job = {
        "id": "test-only-job",
        "conversation_id": first,
        "request_id": "test-only-request",
        "status": "error",
        "created_at": "2026-11-18T00:00:00Z",
        "updated_at": "2026-11-18T00:01:00Z",
        "events": [
            {"type": "started", "user_message_id": user},
            {"type": "report", "report": report},
        ],
        "error": {"code": "test-only-error", "message": "Explicit test-only failure"},
    }
    with store.connection() as db:
        db.execute(
            "INSERT INTO v45_jobs VALUES(?,?,?,?,?)",
            (
                job["id"],
                first,
                job["request_id"],
                "test-only-signature",
                json.dumps(job),
            ),
        )
    response = client.get(
        "/api/v1/frontend/investigations",
        params={"query": "job question", "status": "error"},
    ).json()
    assert response["total"] == 1 and response["items"][0]["id"] == job["id"]
    assert response["items"][0]["conversation_id"] == first != second
    assert "job" not in response["items"][0] and "report" not in response["items"][0]
    detail = client.get("/api/v1/frontend/investigations/" + job["id"]).json()
    assert detail["job"]["error"]["code"] == "test-only-error"
    assert detail["report"]["id"] == case_id
    assert (
        client.get("/api/v1/frontend/investigations/" + case_id).json()["id"]
        == job["id"]
    )
    assert (
        client.get("/api/v1/frontend/investigations/missing-test-only-case").status_code
        == 404
    )


def test_image_original_remains_an_actual_scoped_attachment(v2client):
    import io
    from PIL import Image

    cid = v2client.post("/api/v1/conversations", json={}).json()["id"]
    content = io.BytesIO()
    Image.new("RGB", (3, 3), (5, 15, 25)).save(content, format="PNG")
    response = v2client.post(
        "/api/v1/attachments",
        data={"conversation_id": cid},
        files={"file": ("explicit-test-only.png", content.getvalue(), "image/png")},
    )
    assert response.status_code == 200
    item = response.json()
    preview = v2client.get("/api/v1/attachments/" + item["id"] + "/content")
    assert preview.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(preview.content)).size == (3, 3)
    page = v2client.get("/api/v1/frontend/attachments", params={"kind": "image"}).json()
    assert page["total"] == 1 and page["items"][0]["conversation_id"] == cid


def test_brand_assets_are_served_as_svg_instead_of_the_spa(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.main import create_app
    from app.core import config

    static = tmp_path / "static_site"
    (static / "brand").mkdir(parents=True)
    (static / "index.html").write_text("Explicit test-only SPA", encoding="utf-8")
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2 2"></svg>'
    (static / "brand/circuit-s.svg").write_text(svg, encoding="utf-8")
    monkeypatch.setattr(config, "WEB_DIST", static)
    with TestClient(create_app(tmp_path / "state", probe_model=False)) as client:
        response = client.get("/brand/circuit-s.svg")
        assert response.headers["content-type"].startswith("image/svg+xml")
        assert response.text == svg
        assert client.get("/brand/missing-test-only.svg").status_code == 404


def test_audio_original_uses_its_real_media_type_and_inline_disposition(
    v2client, tmp_path
):
    import hashlib
    import wave
    from app.storage.database import now

    store = v2client.app.state.store
    cid = store.create_conversation("Explicit test-only PCM source")["id"]
    path = tmp_path / "explicit-test-only.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 160)
    content = path.read_bytes()
    with store.connection() as db:
        db.execute(
            "INSERT INTO attachments VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "test-only-pcm",
                cid,
                path.name,
                "audio",
                "audio/wav",
                hashlib.sha256(content).hexdigest(),
                str(path),
                "{}",
                now(),
            ),
        )
    response = v2client.get("/api/v1/attachments/test-only-pcm/content")
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.headers["content-disposition"].startswith("inline")
    assert response.content == content
