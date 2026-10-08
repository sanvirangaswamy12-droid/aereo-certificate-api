"""Certificate rendering using ONE predefined template (landscape A4 PDF)."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from .validation import RecipientData

ORGANISATION = "Aereo Academy"


def render_certificate(data: RecipientData, output_path: Path) -> None:
    """Draw the certificate for one recipient and save it to output_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = landscape(A4)
    c = canvas.Canvas(str(output_path), pagesize=landscape(A4))
    c.setTitle(f"Certificate - {data.name}")

    # Double border
    c.setStrokeColor(colors.HexColor("#1F3A5F"))
    c.setLineWidth(6)
    c.rect(25, 25, width - 50, height - 50)
    c.setLineWidth(1.5)
    c.rect(38, 38, width - 76, height - 76)

    # Heading
    c.setFillColor(colors.HexColor("#1F3A5F"))
    c.setFont("Helvetica-Bold", 40)
    c.drawCentredString(width / 2, height - 130, "CERTIFICATE")
    c.setFont("Helvetica", 18)
    c.drawCentredString(width / 2, height - 160, "OF COMPLETION")

    # Body
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 215, "This is to certify that")

    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(width / 2, height - 270, data.name)
    c.setLineWidth(1)
    c.line(width / 2 - 220, height - 280, width / 2 + 220, height - 280)

    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 320, "has successfully completed the course")
    c.setFont("Helvetica-BoldOblique", 24)
    c.drawCentredString(width / 2, height - 360, data.course_name)

    # Footer
    c.setFont("Helvetica", 13)
    c.drawString(80, 85, f"Date: {data.issue_date.strftime('%d %B %Y')}")
    c.drawRightString(width - 80, 85, ORGANISATION)
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 80, 68, "Authorised signatory")

    c.showPage()
    c.save()
