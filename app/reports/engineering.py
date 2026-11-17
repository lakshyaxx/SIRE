"""Reproducible Markdown/PDF reports assembled exclusively from persisted case/evidence snapshots."""

import io
import json
from xml.sax.saxutils import escape
from app.evidence.ledger import Ledger, digest
from app.knowledge.case_memory import annotations
from app.storage.database import now


def render_markdown(case: dict, evidence: list[dict]) -> str:
    """Render actual scope, chronology, alternative mechanisms and source pointers."""
    lines = [
        "# SIRE engineering investigation",
        "",
        "**SIMULATED FACILITY â€” human review required**",
        f"Case: {case['id']}  ",
        f"Asset: {case['asset_id']}  ",
        f"Report snapshot time: {case['created_at']}  ",
        f"Information cutoff: {case['as_of']}",
        "",
        case["conclusion"],
        "",
        "## Competing mechanisms",
    ]
    for h in case["hypotheses"]:
        lines += [
            f"### {h['mechanism']} ({h['status']})",
            f"Heuristic ordering score: {h['score']}; not a probability.",
            "Support: " + (", ".join(h["support"]) or "None established"),
            "Conflicts: " + (", ".join(h["contradictions"]) or "None established"),
            "Missing measurements: "
            + (
                "; ".join(h["missing_measurements"])
                or "Independent inspection still required"
            ),
            "Next checks: " + "; ".join(h["next_checks"]),
            "",
        ]
    lines += [
        "## Observed telemetry summaries",
        "| Asset/channel | Baseline mean | Recent mean | Change | Unit |",
        "| --- | ---: | ---: | ---: | --- |",
    ]

    def display(value: float | None) -> str:
        return f"{value:.4g}" if value is not None else "unavailable"

    for summary in case["summaries"]:
        for channel, row in summary["channels"].items():
            lines.append(
                f"| {summary['asset_id']}/{channel} | {display(row['baseline_mean'])} | {display(row['recent_mean'])} | {display(row['delta'])} | {row['unit']} |"
            )
    lines += ["", "## Available maintenance / event chronology"]
    for event in case["timeline"]:
        lines.append(
            f"- {event['observed_at']} / available {event['available_at']}: {event['text']} [{event['evidence_id']}]"
        )
    lines += ["", "## Evidence ledger"]
    for row in evidence:
        e = row["evidence"]
        lines.append(
            f"- {e['id']} | {row['source']['name']} | {json.dumps(e['pointer'],sort_keys=True)} | SHA256 {e['sha256']}"
        )
    lines += (
        [
            "",
            "## Operational trace",
            f"Run {case['run_id']}; stop {case['stop_reason']}; {len(case['rounds'])} rounds.",
            "",
            "## Limitations / review",
        ]
        + ["- " + text for text in case["limitations"]]
        + [
            "- Confirmation status: " + case["confirmation_status"],
            "- Suggestions are inspection/review requests, not control instructions.",
            "- No C-MAPSS prediction was invoked for this synthetic plant.",
        ]
    )
    return "\n".join(lines) + "\n"


def create(ledger: Ledger, case_id: str) -> dict:
    """Freeze source snapshots and a content-derived report ID; unchanged input reproduces exactly."""
    case = ledger.get("cases", case_id)
    evidence = [ledger.resolve(i) for i in case["evidence_ids"]]
    markdown = render_markdown(case, evidence)
    reviews = annotations(ledger, case_id)
    if reviews:
        markdown += "\n## Manually entered review notes (unverified assertions)\n"
        markdown += (
            "\n".join(
                f"- {r['created_at']} [{r['review_status']}]: {r['note']}"
                for r in reviews
            )
            + "\n"
        )
    signature = digest(
        {"case": case, "evidence": evidence, "reviews": reviews, "markdown": markdown}
    )
    identifier = "report-" + signature
    previous = ledger.store.rows(
        "SELECT payload FROM v3_reports WHERE id=?", (identifier,)
    )
    if previous:
        return json.loads(previous[0]["payload"])
    created = now()
    first, rest = markdown.split("\n", 1)
    markdown = first + f"\n\nReport ID: {identifier}\nCreated UTC: {created}\n" + rest
    payload = {
        "case_id": case_id,
        "case": case,
        "evidence": evidence,
        "markdown": markdown,
        "created_at": created,
        "review_annotations": reviews,
        "sha256": digest({"case": case, "evidence": evidence, "markdown": markdown}),
        "human_review_status": (
            reviews[-1]["review_status"] if reviews else "unreviewed"
        ),
        "source_type": case["source_type"],
    }
    payload["id"] = identifier
    ledger.save("reports", payload, payload["id"])
    return payload


def pdf_bytes(report: dict) -> bytes:
    """Produce a genuine paginated report from saved content; no external downloads or static example."""
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.lib import colors
    from reportlab.pdfgen.canvas import Canvas
    from functools import partial

    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    story = []
    table_rows = []

    def flush_table() -> None:
        """Render actual Markdown table cells as a repeating-header report table."""
        if not table_rows:
            return
        cell_style = styles["BodyText"].clone("cell")
        cell_style.fontSize = 7
        cell_style.leading = 9
        cells = [
            [
                Paragraph(
                    ("<b>" + escape(c) + "</b>") if i == 0 else escape(c), cell_style
                )
                for c in row
            ]
            for i, row in enumerate(table_rows)
        ]
        table = Table(
            cells, colWidths=[160, 82, 82, 82, 54], repeatRows=1, hAlign="LEFT"
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3f0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(table)
        table_rows.clear()

    for line in report["markdown"].splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not all(set(c) <= {"-", ":", " "} for c in cells):
                table_rows.append(cells)
            continue
        flush_table()
        if not line.strip():
            story.append(Spacer(1, 6))
            continue
        style = (
            styles["Heading1"]
            if line.startswith("# ")
            else (
                styles["Heading2"]
                if line.startswith("## ")
                else (
                    styles["Heading3"]
                    if line.startswith("### ")
                    else styles["BodyText"]
                )
            )
        )
        # Long immutable citation hashes wrap inside narrow pages without clipping.
        style = style.clone("report-" + style.name)
        style.splitLongWords = True
        style.fontSize = min(style.fontSize, 16)
        style.keepWithNext = line.startswith("#")
        plain = (
            line.lstrip("# ")
            .replace("**", "")
            .replace("â€”", "-")
            .replace("â€“", "-")
            .encode("ascii", "backslashreplace")
            .decode()
        )
        story.append(Paragraph(escape(plain), style))
    flush_table()
    SimpleDocTemplate(
        buffer,
        title="SIRE engineering evidence report",
        author="SIRE local prototype",
        pageCompression=1,
        invariant=1,
    ).build(story, canvasmaker=partial(Canvas, invariant=1))
    return buffer.getvalue()
