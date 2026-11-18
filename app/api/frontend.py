"""Read-only, paginated presentation indexes over existing local application records."""

import json
from pathlib import Path
from fastapi import APIRouter, Query, Request
from app.core.config import SETTINGS
from app.core.errors import SireError
from app.storage.database import now
from app.orchestration.understanding import target_asset

router = APIRouter(prefix="/api/v1/frontend", tags=["frontend"])
UPLOAD_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".pdf",
    ".txt",
    ".md",
    ".json",
    ".docx",
    ".xlsx",
    ".csv",
    ".wav",
    ".flac",
    ".ogg",
    ".mp3",
    ".mp4",
    ".mov",
    ".avi",
    ".webm",
    ".mkv",
)


@router.get("/config")
def config(request: Request) -> dict:
    """Expose existing intake bounds and server time without executing a model."""
    return {
        "application_version": request.app.version,
        "checked_at": now(),
        "upload_extensions": list(UPLOAD_EXTENSIONS),
        "max_upload_bytes": SETTINGS["max_upload_bytes"],
        "max_message_attachments": 6,
        "max_message_images": 3,
        "report_formats": ["pdf", "markdown"],
    }


@router.get("/attachments")
def attachments(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    conversation_id: str | None = None,
    query: str = Query("", max_length=200),
    kind: str = Query("", max_length=20),
) -> dict:
    """Page catalogued uploads, omitting private filesystem paths and file bytes."""
    store = request.app.state.store
    conditions, values = [], []
    if conversation_id:
        conditions.append("conversation_id=?")
        values.append(conversation_id)
    if query:
        conditions.append("name LIKE ?")
        values.append("%" + query + "%")
    if kind:
        conditions.append("kind=?")
        values.append(kind)
    clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    args = tuple(values)
    if conversation_id:
        store.conversation(conversation_id)
    total = store.rows("SELECT COUNT(*) AS total FROM attachments" + clause, args)[0][
        "total"
    ]
    rows = store.rows(
        "SELECT id,conversation_id,name,kind,mime,sha256,metadata,created_at,path FROM attachments"
        + clause
        + " ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
        (*args, page_size, (page - 1) * page_size),
    )
    for row in rows:
        row["metadata"] = json.loads(row["metadata"])
        path = Path(row.pop("path"))
        row["size_bytes"] = row["metadata"].get("size_bytes")
        if row["size_bytes"] is None and path.is_file():
            row["size_bytes"] = path.stat().st_size
    return {"items": rows, "page": page, "page_size": page_size, "total": total}


@router.get("/attachments/{identifier}")
def attachment(identifier: str, request: Request) -> dict:
    """Resolve an original catalogued file from a canonical citation, beyond the first page."""
    row = request.app.state.store.attachment(identifier)
    path = Path(row.pop("path"))
    row["size_bytes"] = row["metadata"].get("size_bytes")
    if row["size_bytes"] is None and path.is_file():
        row["size_bytes"] = path.stat().st_size
    return row


def _records(request: Request) -> list[dict]:
    """Read saved general cases and durable jobs; never manufacture completed records."""
    store = request.app.state.store
    rows = []
    for row in store.rows(
        "SELECT id,conversation_id,payload,created_at FROM cases ORDER BY created_at DESC"
    ):
        report = json.loads(row["payload"])
        rows.append(
            {
                "id": row["id"],
                "kind": "case",
                "conversation_id": row["conversation_id"],
                "created_at": row["created_at"],
                "updated_at": row["created_at"],
                "status": "complete",
                "question": report["case"]["question"],
                "evidence_count": len(report["case"]["evidence"]),
                "report": report,
            }
        )
    for row in store.rows("SELECT payload FROM v45_jobs ORDER BY rowid DESC"):
        job = json.loads(row["payload"])
        report = next(
            (
                e["report"]
                for e in reversed(job["events"])
                if e.get("type") == "report" and e.get("report")
            ),
            None,
        )
        if report and report.get("id") in {r["id"] for r in rows}:
            rows = [r for r in rows if r["id"] != report["id"]]
        messages = store.messages(job["conversation_id"])
        user_message = next(
            (
                m
                for m in messages
                if m.get("metadata", {}).get("request_id") == job["request_id"]
                and m["role"] == "user"
            ),
            None,
        )
        if user_message is None:
            user_id = next(
                (
                    e.get("user_message_id")
                    for e in job["events"]
                    if e.get("type") == "started"
                ),
                None,
            )
            user_message = next((m for m in messages if m["id"] == user_id), None)
        submitted = job.get("request") or {}
        question = (
            user_message["content"] if user_message else submitted.get("content", "")
        )
        attachment_ids = submitted.get(
            "attachment_ids",
            (user_message or {}).get("metadata", {}).get("attachments", []),
        )
        requested_asset = target_asset(question, [])
        partial_evidence = next(
            (
                e["evidence"]
                for e in reversed(job["events"])
                if e.get("type") == "evidence" and e.get("evidence")
            ),
            [],
        )
        failure = dict(job.get("error") or {})
        if failure and not failure.get("stage"):
            failure["stage"] = (
                "routing"
                if failure.get("code") == "rul_requires_sensor_tool"
                else "not recorded"
            )
        attached = []
        for attachment_id in attachment_ids:
            try:
                item = store.attachment(attachment_id, job["conversation_id"])
                attached.append(
                    {key: item[key] for key in ("id", "name", "kind", "sha256")}
                )
            except SireError:
                attached.append(
                    {
                        "id": attachment_id,
                        "name": "Source unavailable",
                        "kind": "unknown",
                        "missing": True,
                    }
                )
        rows.append(
            {
                "id": job["id"],
                "kind": "job",
                "conversation_id": job["conversation_id"],
                "created_at": job["created_at"],
                "updated_at": job["updated_at"],
                "status": job["status"],
                "question": question,
                "evidence_count": (
                    len(report["case"]["evidence"]) if report else len(partial_evidence)
                ),
                "report": report,
                "job": job,
                "attachment_ids": attachment_ids,
                "attachments": attached,
                "requested_asset_id": requested_asset,
                "asset_identity_source": "user_question" if requested_asset else None,
                "partial_evidence": partial_evidence,
                "failure": failure or None,
            }
        )
    return sorted(rows, key=lambda row: row["updated_at"], reverse=True)


@router.get("/investigations")
def investigations(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    query: str = Query("", max_length=200),
    status: str = Query("", max_length=30),
) -> dict:
    """Return real lifecycle summaries, with pagination and no full report bodies."""
    records = [
        r
        for r in _records(request)
        if (not query or query.casefold() in r["question"].casefold())
        and (not status or r["status"] == status)
    ]
    items = [
        {k: v for k, v in row.items() if k not in {"report", "job"}}
        for row in records[(page - 1) * page_size : page * page_size]
    ]
    return {"items": items, "page": page, "page_size": page_size, "total": len(records)}


@router.get("/investigations/{identifier}")
def investigation(identifier: str, request: Request) -> dict:
    """Resolve an actual saved case or job; raw sources stay in their existing ledger."""
    record = next(
        (
            r
            for r in _records(request)
            if r["id"] == identifier or (r.get("report") or {}).get("id") == identifier
        ),
        None,
    )
    if record is None:
        raise SireError("investigation_missing", "Saved investigation not found.", 404)
    return record
