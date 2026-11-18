"""Deterministic numeric column summaries of actual CSV and safe XLSX cells."""

from collections import defaultdict
import csv
import io
import math
import re
from statistics import mean
import zipfile
from app.evidence.formats import _xml, sections


def summarize(content: bytes, suffix: str) -> list[dict]:
    """Compute finite numeric values directly; never infer units, assets or faults."""
    tables = []
    if suffix == ".csv":
        sections(content, suffix)  # Reuse the existing bounded structured validator.
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        rows = list(reader)
        columns = []
        for name in reader.fieldnames or []:
            values = []
            for index, row in enumerate(rows, 2):
                try:
                    value = float(row[name])
                except (ValueError, TypeError):
                    continue
                if math.isfinite(value):
                    values.append((f"record {index-1} / field {name}", value))
            if values:
                columns.append(_summary(name, values))
        tables.append(
            {"table": "CSV", "data_rows": len(rows), "numeric_columns": columns}
        )
    elif suffix == ".xlsx":
        sections(
            content, suffix
        )  # ZIP/XML limits, external relationships and formulas checked.
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            shared = []
            if "xl/sharedStrings.xml" in z.namelist():
                shared = [
                    "".join(t.text or "" for t in item.iter("{" + ns["s"] + "}t"))
                    for item in _xml(z.read("xl/sharedStrings.xml"))
                ]
            targets = {
                r.attrib["Id"]: r.attrib["Target"]
                for r in _xml(z.read("xl/_rels/workbook.xml.rels"))
                if r.attrib.get("TargetMode") != "External"
            }
            for sheet in _xml(z.read("xl/workbook.xml")).findall(
                "s:sheets/s:sheet", ns
            ):
                target = targets[
                    sheet.attrib[
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                    ]
                ]
                member = (
                    target.lstrip("/") if target.startswith("/") else "xl/" + target
                )
                rows = _xml(z.read(member)).findall(".//s:row", ns)
                columns = defaultdict(list)
                headers = {}
                for index, row in enumerate(rows):
                    for cell in row.findall("s:c", ns):
                        coordinate = cell.attrib.get("r", "")
                        match = re.fullmatch(r"([A-Z]+)[0-9]+", coordinate)
                        if not match or cell.find("s:f", ns) is not None:
                            continue
                        name = match[1]
                        raw = cell.findtext("s:v", default="", namespaces=ns)
                        kind = cell.attrib.get("t", "n")
                        if index == 0:
                            if kind == "s":
                                raw = shared[int(raw)]
                            elif kind == "inlineStr":
                                raw = "".join(
                                    t.text or "" for t in cell.findall(".//s:t", ns)
                                )
                            headers[name] = raw
                            if kind != "n":
                                continue
                        if kind == "n":
                            try:
                                value = float(raw)
                            except ValueError:
                                continue
                            if math.isfinite(value):
                                columns[name].append(
                                    (
                                        f'sheet {sheet.attrib["name"]} / cell {coordinate}',
                                        value,
                                    )
                                )
                tables.append(
                    {
                        "table": sheet.attrib["name"],
                        "source_rows": len(rows),
                        "numeric_columns": [
                            _summary(headers.get(k) or k, v)
                            for k, v in sorted(columns.items())
                        ],
                    }
                )
    return tables


def _summary(name: str, values: list[tuple[str, float]]) -> dict:
    numbers = [v for _, v in values]
    return {
        "column": name,
        "count": len(numbers),
        "minimum": min(numbers),
        "maximum": max(numbers),
        "mean": mean(numbers),
        "source_locators": [p for p, _ in values],
        "unit": "not inferred",
        "interpretation": "Numeric cell values only; missing/non-numeric/formula cells excluded; no fault inference.",
    }
