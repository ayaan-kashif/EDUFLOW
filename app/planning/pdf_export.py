"""Paginated, readable PDF export of a saved term plan."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def render_plan_pdf(rows):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(595, 842),
        rightMargin=36,
        leftMargin=36,
        topMargin=42,
        bottomMargin=42,
        title="EduFlow Term Plan",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("EduFlow | Term plan", styles["Title"]),
        Paragraph(
            "Saved schedule. Local timetable times. Class-level planning with no student records.",
            styles["Normal"],
        ),
        Spacer(1, 0.2 * inch),
    ]
    cells = [["Date", "Time", "Lesson", "Minutes", "Status"]]
    for su, node, win, day in rows:
        cells.append(
            [
                str(day.date),
                win.start_time.strftime("%H:%M"),
                Paragraph(escape(node.label), styles["Normal"]),
                str(su.scheduled_minutes),
                su.status.value,
            ]
        )
    table = Table(cells, colWidths=[76, 45, 245, 55, 102], repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#394e39")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f4ee")]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dde1d5")),
            ]
        )
    )
    story.append(table)

    def footer(canvas, document):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#657065"))
        canvas.drawString(36, 24, "EduFlow - Evidence before eloquence")
        canvas.drawRightString(559, 24, str(document.page))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
