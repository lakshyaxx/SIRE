"""Real extraction and strict validation; synthetic fixtures are unit-test only."""

import io
import pytest
from PIL import Image
from reportlab.pdfgen import canvas
from app.core.errors import SireError
from app.knowledge.ingestion import ingest, csv_history, extract_document
from app.knowledge.search import search
from app.prediction.telemetry import asset_history


def test_citations_match_actual_text(store):
    c = store.create_conversation()
    content = b"Test-only maintenance note\nObserved corrosion during inspection.\nNo operation is authorized."
    item = ingest(store, c["id"], "../maintenance.txt", content)
    results = search(store, c["id"], "corrosion inspection")
    assert item["name"] == "maintenance.txt"
    assert results and "lines 1-3" in results[0]["locator"]
    assert results[0]["excerpt"] in content.decode()
    assert search(store, c["id"], "corrosion") == search(store, c["id"], "corrosion")


def test_pdf_page_citation():
    data = io.BytesIO()
    pdf = canvas.Canvas(data)
    pdf.drawString(50, 700, "Test-only inspection record.")
    pdf.showPage()
    pdf.save()
    pages = extract_document(data.getvalue(), ".pdf")
    assert pages[0][0] == "page 1"
    assert "Test-only inspection record" in pages[0][1]


@pytest.mark.parametrize(
    "name,content",
    [
        ("a.jpg", b"bad image"),
        ("a.pdf", b"bad PDF"),
        ("a.csv", b"a,a\n1,2"),
        ("a.exe", b"MZ"),
    ],
)
def test_corrupted_uploads_fail(store, name, content):
    c = store.create_conversation()
    with pytest.raises(SireError):
        ingest(store, c["id"], name, content)
    assert store.attachments(c["id"]) == []


def test_image_metadata_removed(store):
    image = Image.new("RGB", (3, 3))
    content = io.BytesIO()
    image.save(content, format="PNG")
    c = store.create_conversation()
    a = ingest(store, c["id"], "pixel.png", content.getvalue())
    assert a["kind"] == "image" and a["mime"] == "image/jpeg"
    with Image.open(store.attachment(a["id"])["path"]) as normalized:
        assert not normalized.getexif()


def test_csv_domain_mapping_and_restart(store):
    frame = asset_history("FD002-ENGINE-001", "FD002")
    a = ingest(
        store, None, "fd002.csv", frame.to_csv(index=False).encode(), "FD002", True
    )
    assert a["metadata"]["prediction_eligible"]
    assert len(csv_history(store, a["id"], "FD002")) == len(frame)
    with pytest.raises(SireError):
        csv_history(store, a["id"], "FD001")
    b = ingest(store, None, "rig.csv", b"vibration,pressure\n0.1,3.2\n", "FD002", True)
    assert not b["metadata"]["prediction_eligible"]
    with pytest.raises(SireError):
        csv_history(store, b["id"], "FD002")


def test_cross_conversation_attachment_refused(store):
    a, b = store.create_conversation(), store.create_conversation()
    item = ingest(store, a["id"], "a.txt", b"Test-only document")
    with pytest.raises(SireError):
        store.attachment(item["id"], b["id"])
