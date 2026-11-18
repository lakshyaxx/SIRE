"""Test-only small numeric tables; no diagnostic accuracy claim from these fixtures."""

import io
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.evidence.tabular import summarize


def workbook() -> bytes:
    """Construct a deliberately labeled test-only workbook with a formula to exclude."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="TEST-ONLY" r:id="rId1"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        z.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>TEST-ONLY value</t></is></c></row><row r="2"><c r="A2"><v>2</v></c></row><row r="3"><c r="A3"><v>4</v></c></row><row r="4"><c r="A4"><f>99+99</f><v>198</v></c></row></sheetData></worksheet>',
        )
    return stream.getvalue()


def test_real_cell_summary_excludes_formula_and_retains_coordinates() -> None:
    column = summarize(workbook(), ".xlsx")[0]["numeric_columns"][0]
    assert (
        column["column"] == "TEST-ONLY value"
        and column["mean"] == 3
        and column["count"] == 2
    )
    assert column["source_locators"] == [
        "sheet TEST-ONLY / cell A2",
        "sheet TEST-ONLY / cell A3",
    ]
    assert column["unit"] == "not inferred"


def test_document_specialist_extracts_actual_csv_and_workbook(tmp_path: Path) -> None:
    with TestClient(create_app(state_dir=tmp_path, probe_model=False)) as c:
        cid = c.post("/api/v1/conversations", json={}).json()["id"]
        for index, (name, data) in enumerate(
            [("test-only.csv", b"value\n2\n4\n"), ("test-only.xlsx", workbook())]
        ):
            upload = c.post(
                "/api/v1/attachments",
                data={"conversation_id": cid},
                files={"file": (name, data)},
            )
            assert upload.status_code == 200, upload.text
            r = c.post(
                "/api/v1/specialists/execute",
                json={
                    "conversation_id": cid,
                    "request_id": str(index),
                    "tool_id": "document.extract",
                    "arguments": {"attachment_id": upload.json()["id"]},
                },
            )
            assert r.status_code == 200, r.text
            result = r.json()["output"]
            assert result["tables"][0]["numeric_columns"][0]["mean"] == 3
            assert (
                result["sections"]
                and result["statistics_evidence_id"] in result["evidence_ids"]
            )
