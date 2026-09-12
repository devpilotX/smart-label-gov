"""Portable reports built from the same InspectionResult the UI shows."""

import html
import json
from io import BytesIO

from .models import FIELD_LABELS, InspectionResult

HTML_STYLE = """
body{font-family:Inter,Arial,Helvetica,sans-serif;color:#17283d;max-width:960px;margin:40px auto;padding:0 20px;line-height:1.45}
h1{font-size:26px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}
.meta{color:#64748b;font-size:13px}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700}
.screened,.pass{background:#e3f7ef;color:#0f7a5c}
.needs_attention,.review{background:#fff3d6;color:#8a5a00}
.potential_issue,.fail{background:#fde5e5;color:#a12c2c}
.not_applicable{background:#eef2f7;color:#64748b}
table{border-collapse:collapse;width:100%;margin:10px 0}
td,th{border-bottom:1px solid #dce4ed;padding:9px 10px;text-align:left;font-size:13px;vertical-align:top}
th{background:#f4f7fb;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#64748b}
.ev{color:#64748b;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}
.summary{display:flex;gap:14px;flex-wrap:wrap;margin:14px 0}
.summary div{background:#f4f7fb;border-radius:10px;padding:10px 14px;min-width:120px}
.summary b{display:block;font-size:20px}
.footer{margin-top:30px;padding-top:12px;border-top:1px solid #dce4ed}
@media print{body{margin:0}}
"""


def json_bytes(result: InspectionResult) -> bytes:
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False).encode("utf-8")


def html_bytes(result: InspectionResult) -> bytes:
    def esc(value: object) -> str:
        return html.escape(str(value))

    check_rows = "".join(
        f"<tr><td>{esc(check.title)}</td>"
        f"<td><span class='badge {esc(check.status)}'>{esc(check.status_label)}</span></td>"
        f"<td>{esc(check.message)}</td></tr>"
        for check in result.checks
    )
    field_rows = "".join(
        f"<tr><td>{esc(FIELD_LABELS.get(name, name))}</td><td>{esc(field.display_value)}</td>"
        f"<td>{field.confidence:.0%}</td><td class='ev'>{esc(field.source_text)}</td></tr>"
        for name, field in result.fields.items()
    ) or "<tr><td colspan='4' class='meta'>No fields were extracted.</td></tr>"
    warnings_block = ""
    if result.warnings:
        items = "".join(f"<li>{esc(warning)}</li>" for warning in result.warnings)
        warnings_block = f"<h2>Warnings</h2><ul>{items}</ul>"
    unit_price = result.unit_price
    unit_price_text = f"\u20b9{unit_price['value']:,.2f} per {esc(unit_price['unit'])}" if unit_price else "Not calculated"

    document = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>SmartLabel report {esc(result.inspection_id)}</title>"
        f"<style>{HTML_STYLE}</style></head><body>"
        "<h1>SmartLabel Inspector</h1>"
        f"<p class='meta'>Inspection {esc(result.inspection_id)} &middot; {esc(result.created_at)} &middot; "
        f"Source {esc(result.source)} &middot; Rule set {esc(result.rule_set)}</p>"
        f"<p><span class='badge {esc(result.overall_status)}'>{esc(result.status_label)}</span></p>"
        "<div class='summary'>"
        f"<div><b>{result.pass_count}/{result.applicable_count}</b>checks passed</div>"
        f"<div><b>{result.review_count}</b>need attention</div>"
        f"<div><b>{len(result.fields)}</b>fields detected</div>"
        f"<div><b>{result.ocr_confidence:.0%}</b>confidence</div>"
        "</div>"
        f"<p><b>Context:</b> {esc(result.product_context)} &middot; <b>Sold by:</b> {esc(result.sold_by)} "
        f"&middot; <b>Unit price:</b> {unit_price_text}</p>"
        f"{warnings_block}"
        "<h2>Detected fields</h2><table><tr><th>Field</th><th>Value</th><th>Confidence</th><th>Evidence</th></tr>"
        f"{field_rows}</table>"
        "<h2>Checks</h2><table><tr><th>Check</th><th>Status</th><th>Message</th></tr>"
        f"{check_rows}</table>"
        "<p class='meta footer'>This report is a screening aid generated from visible label text. "
        "It is not a legal certificate and does not replace a qualified decision-maker.</p>"
        "</body></html>"
    )
    return document.encode("utf-8")


def _pdf_safe(value: object) -> str:
    """Core PDF fonts cover Latin-1 only, so swap the few symbols we use."""
    text = str(value).replace("\u20b9", "Rs. ").replace("\u00b7", "-").replace("\u2014", "-").replace("\u2013", "-")
    return html.escape(text.encode("latin-1", "replace").decode("latin-1"), quote=False)


def pdf_bytes(result: InspectionResult) -> bytes:
    """Build a compact A4 PDF with reportlab."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    ink = colors.HexColor("#17283d")
    muted_ink = colors.HexColor("#64748b")
    title = ParagraphStyle("sl_title", parent=styles["Title"], fontSize=20, leading=24, alignment=TA_LEFT, textColor=ink, spaceAfter=2)
    body = ParagraphStyle("sl_body", parent=styles["BodyText"], fontSize=9.5, leading=13, textColor=ink)
    muted = ParagraphStyle("sl_muted", parent=body, fontSize=8.5, leading=11, textColor=muted_ink)
    heading = ParagraphStyle("sl_heading", parent=styles["Heading2"], fontSize=12.5, leading=15, textColor=ink, spaceBefore=10, spaceAfter=4)
    cell = ParagraphStyle("sl_cell", parent=body, fontSize=8.5, leading=11)
    head_cell = ParagraphStyle("sl_head_cell", parent=cell, fontName="Helvetica-Bold", textColor=muted_ink)

    def table(rows: list[list], widths: list[float]) -> Table:
        built = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        built.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f7fb")),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce4ed")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return built

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"SmartLabel report {result.inspection_id}",
        author="SmartLabel Inspector",
    )
    width = A4[0] - 32 * mm
    unit_price = result.unit_price
    unit_price_text = f"Rs. {unit_price['value']:,.2f} per {unit_price['unit']}" if unit_price else "Not calculated"

    story = [
        Paragraph("SmartLabel Inspector", title),
        Paragraph(
            f"Inspection {_pdf_safe(result.inspection_id)} | {_pdf_safe(result.created_at)} | "
            f"Source {_pdf_safe(result.source)} | Rule set {_pdf_safe(result.rule_set)}",
            muted,
        ),
        Spacer(1, 8),
        Paragraph(
            f"<b>Status:</b> {_pdf_safe(result.status_label)} | <b>Checks passed:</b> "
            f"{result.pass_count}/{result.applicable_count} | <b>Needs attention:</b> {result.review_count} | "
            f"<b>Confidence:</b> {result.ocr_confidence:.0%}",
            body,
        ),
        Paragraph(
            f"<b>Context:</b> {_pdf_safe(result.product_context)} | <b>Sold by:</b> {_pdf_safe(result.sold_by)} | "
            f"<b>Unit price:</b> {_pdf_safe(unit_price_text)}",
            body,
        ),
    ]
    if result.warnings:
        story.append(Paragraph("Warnings", heading))
        story.extend(Paragraph(f"- {_pdf_safe(warning)}", body) for warning in result.warnings)

    story.append(Paragraph("Detected fields", heading))
    field_rows: list[list] = [
        [Paragraph("Field", head_cell), Paragraph("Value", head_cell), Paragraph("Confidence", head_cell), Paragraph("Evidence", head_cell)]
    ]
    for name, field in result.fields.items():
        field_rows.append(
            [
                Paragraph(_pdf_safe(FIELD_LABELS.get(name, name)), cell),
                Paragraph(_pdf_safe(field.display_value), cell),
                Paragraph(f"{field.confidence:.0%}", cell),
                Paragraph(_pdf_safe(field.source_text), cell),
            ]
        )
    if len(field_rows) == 1:
        field_rows.append([Paragraph("No fields were extracted.", cell), "", "", ""])
    story.append(table(field_rows, [width * 0.20, width * 0.22, width * 0.13, width * 0.45]))

    story.append(Paragraph("Checks", heading))
    check_rows: list[list] = [[Paragraph("Check", head_cell), Paragraph("Status", head_cell), Paragraph("Message", head_cell)]]
    for check in result.checks:
        check_rows.append(
            [
                Paragraph(_pdf_safe(check.title), cell),
                Paragraph(_pdf_safe(check.status_label), cell),
                Paragraph(_pdf_safe(check.message), cell),
            ]
        )
    story.append(table(check_rows, [width * 0.25, width * 0.15, width * 0.60]))

    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "This report is a screening aid generated from visible label text. It is not a legal certificate "
            "and does not replace a qualified decision-maker.",
            muted,
        )
    )
    document.build(story)
    return buffer.getvalue()
