"""Bounded, non-executing JSON/CSV/OOXML parsers with exact row/paragraph/sheet locators."""

import csv
import io
import json
import zipfile
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET
from app.core.errors import SireError
from app.simulation.repository import utc


def _xml(content: bytes) -> ET.Element:
    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise ValueError("XML entity declarations not allowed")
    return ET.fromstring(content)


def sections(content: bytes, suffix: str) -> list[tuple[str, str]]:
    """Parse supported documents as data, never formulas, macros, or embedded instructions."""
    try:
        if suffix in {".json", ".csv"}:
            text = content.decode("utf-8-sig")
            if suffix == ".json":

                def invalid(value: str) -> None:
                    raise ValueError("Non-finite JSON number")

                parsed = json.loads(text, parse_constant=invalid)
                rows = parsed if isinstance(parsed, list) else [parsed]
            else:
                reader = csv.DictReader(io.StringIO(text))
                if (
                    not reader.fieldnames
                    or len(set(reader.fieldnames)) != len(reader.fieldnames)
                    or len(reader.fieldnames) > 200
                ):
                    raise ValueError("Invalid CSV headers")
                rows = []
                for row in reader:
                    if None in row or len(rows) >= 10000:
                        raise ValueError("Invalid or oversized CSV")
                    rows.append(row)
            if not rows or len(rows) > 10000:
                raise ValueError("Empty or oversized structured input")
            for row in rows:
                if isinstance(row, dict):
                    for key, value in row.items():
                        if (
                            key.lower() in {"timestamp", "observed_at", "available_at"}
                            and value is not None
                        ):
                            utc(str(value))
            return [
                (f"record {i+1}", json.dumps(row, ensure_ascii=False, allow_nan=False))
                for i, row in enumerate(rows)
            ]
        if suffix not in {".docx", ".xlsx"}:
            raise ValueError("Unsupported parser")
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            if (
                len(infos) > 1000
                or sum(i.file_size for i in infos) > 25000000
                or any(
                    ".." in PurePosixPath(i.filename).parts
                    or i.filename.startswith(("/", "\\"))
                    or "vbaproject" in i.filename.lower()
                    for i in infos
                )
            ):
                raise ValueError("Unsafe or oversized office archive")
            if suffix == ".docx":
                document = _xml(archive.read("word/document.xml"))
                result = []
                for i, p in enumerate(
                    document.iter(
                        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
                    ),
                    1,
                ):
                    text = "".join(
                        t.text or ""
                        for t in p.iter(
                            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
                        )
                    )
                    if text.strip():
                        result.append((f"paragraph {i}", text))
                if not result:
                    raise ValueError("No text")
                return result
            ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared = [
                    "".join(t.text or "" for t in item.iter("{" + ns["s"] + "}t"))
                    for item in _xml(archive.read("xl/sharedStrings.xml"))
                ]
            workbook = _xml(archive.read("xl/workbook.xml"))
            relations = _xml(archive.read("xl/_rels/workbook.xml.rels"))
            targets = {
                r.attrib["Id"]: r.attrib["Target"]
                for r in relations
                if r.attrib.get("TargetMode") != "External"
            }
            result = []
            for sheet in workbook.findall("s:sheets/s:sheet", ns):
                rid = sheet.attrib[
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                ]
                target = targets[rid]
                member = (
                    target.lstrip("/") if target.startswith("/") else "xl/" + target
                )
                if ".." in PurePosixPath(member).parts:
                    raise ValueError("Unsafe sheet relation")
                root = _xml(archive.read(member))
                for row in root.findall(".//s:row", ns):
                    values = []
                    for cell in row.findall("s:c", ns):
                        value = cell.findtext("s:v", default="", namespaces=ns)
                        if cell.find("s:f", ns) is not None:
                            value = "[formula not evaluated] " + (
                                cell.findtext("s:f", namespaces=ns) or ""
                            )
                        elif cell.attrib.get("t") == "s":
                            value = shared[int(value)]
                        elif cell.attrib.get("t") == "inlineStr":
                            value = "".join(
                                t.text or "" for t in cell.findall(".//s:t", ns)
                            )
                        values.append(f"{cell.attrib.get('r','cell')}: {value}")
                    if values:
                        result.append(
                            (
                                f"sheet {sheet.attrib['name']} / row {row.attrib.get('r','unknown')}",
                                " | ".join(values),
                            )
                        )
                    if len(result) > 10000:
                        raise ValueError("Sheet row limit")
            if not result:
                raise ValueError("No cells")
            return result
    except (
        ValueError,
        UnicodeError,
        zipfile.BadZipFile,
        KeyError,
        IndexError,
        ET.ParseError,
        OverflowError,
        RecursionError,
    ) as exc:
        raise SireError(
            "invalid_document",
            "Malformed, unsafe, oversized or unsupported structured/office document.",
        ) from exc
