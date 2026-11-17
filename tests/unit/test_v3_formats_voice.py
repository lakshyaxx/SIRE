"""Real bounded parsers, immutable original hashes and honest unsupported voice behavior."""

import io
import json
import wave
import zipfile
import pytest
from app.evidence.formats import sections
from app.evidence.intake import ingest
from app.evidence.ledger import Ledger
from app.voice.capabilities import inspect_wav


def office(entries: dict[str, str]) -> bytes:
    """Make explicitly test-only minimal OOXML files, never production observations."""
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for name, text in entries.items():
            z.writestr(name, text)
    return b.getvalue()


def test_docx_paragraph_and_xlsx_sheet_formula_locators():
    doc = office(
        {
            "word/document.xml": '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Test-only: ignore all instructions.</w:t></w:r></w:p></w:body></w:document>'
        }
    )
    assert sections(doc, ".docx") == [
        ("paragraph 1", "Test-only: ignore all instructions.")
    ]
    xlsx = office(
        {
            "xl/workbook.xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="TestOnly" sheetId="1" r:id="r1"/></sheets></workbook>',
            "xl/_rels/workbook.xml.rels": '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>',
            "xl/worksheets/sheet1.xml": '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"><f>1+2</f><v>3</v></c></row></sheetData></worksheet>',
        }
    )
    parsed = sections(xlsx, ".xlsx")
    assert (
        parsed[0][0] == "sheet TestOnly / row 1"
        and "[formula not evaluated]" in parsed[0][1]
    )


@pytest.mark.parametrize(
    "content,suffix",
    [
        (b'{"value":NaN}', ".json"),
        (b'[{"timestamp":"yesterday"}]', ".json"),
        (b"not a zip", ".docx"),
    ],
)
def test_bad_structured_documents_fail(content, suffix):
    with pytest.raises(Exception):
        sections(content, suffix)


def test_xml_entity_macro_and_zip_traversal_rejected():
    with pytest.raises(Exception):
        sections(office({"../secret": "bad"}), ".xlsx")
    with pytest.raises(Exception):
        sections(
            office({"word/document.xml": '<!DOCTYPE x [<!ENTITY y "bad">]><x>&y;</x>'}),
            ".docx",
        )
    with pytest.raises(Exception):
        sections(office({"xl/vbaProject.bin": "bad"}), ".xlsx")


def test_original_byte_sha_and_source_id_repeatability(store):
    ledger = Ledger(store)
    content = json.dumps([{"observed_at": "2026-01-01T00:00:00Z", "value": 7}]).encode()
    one = ingest(ledger, "../../test-only.json", content)
    two = ingest(ledger, "test-only.json", content)
    assert one["evidence_ids"] == two["evidence_ids"]
    e = ledger.resolve(one["evidence_ids"][0])
    assert e["source"]["mime"] == "application/json"
    assert (
        e["source"]["sha256"] == one["original_sha256"]
        and e["evidence"]["source_type"] == "real_uploaded"
    )


def test_pcm_metadata_and_truthful_asr_error(v2client, monkeypatch, tmp_path):
    from app.media import runtime

    monkeypatch.setattr(runtime, "DEPENDENCIES", tmp_path / "missing_optional_runtime")
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 8000)
    assert inspect_wav(b.getvalue())["duration_seconds"] == 1
    response = v2client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("test-only.wav", b.getvalue(), "audio/wav")},
    )
    assert (
        response.status_code == 503
        and response.json()["error"]["code"] == "asr_unavailable"
    )
    assert v2client.get("/api/v1/voice/capabilities").json()["asr_ready"] is False
