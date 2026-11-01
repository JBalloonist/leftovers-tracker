"""Render QR-code labels to PDF, for Avery sheets or a roll label printer."""
import io

import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch, mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# Avery 8460 (same layout as 5160): 30 labels per US Letter sheet, 2.625" x 1".
SHEET = dict(cols=3, rows=10, width=2.625 * inch, height=1 * inch,
             left=0.1875 * inch, top=0.5 * inch, col_pitch=2.75 * inch)

# Roll printers: one label per PDF page. 62 x 29 mm fits Brother DK-1209;
# for Dymo 30252 use 89 x 28 mm.
ROLL_SIZE = (62 * mm, 29 * mm)


def _qr_image(data):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image().save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _draw_label(c, x, y, w, h, code, base_url):
    pad = 0.06 * inch
    qr_size = h - 2 * pad
    c.drawImage(_qr_image(f"{base_url}/l/{code}"), x + pad, y + pad, qr_size, qr_size)
    text_x = x + qr_size + 2 * pad
    c.setFont("Helvetica-Bold", 14)
    c.drawString(text_x, y + h / 2 + 2, code)
    c.setFont("Helvetica", 7)
    c.drawString(text_x, y + h / 2 - 10, "Scan to log leftovers")


def render_pdf(codes, base_url, fmt="sheet"):
    buf = io.BytesIO()
    if fmt == "roll":
        w, h = ROLL_SIZE
        c = canvas.Canvas(buf, pagesize=(w, h))
        for code in codes:
            _draw_label(c, 0, 0, w, h, code, base_url)
            c.showPage()
    else:
        c = canvas.Canvas(buf, pagesize=letter)
        per_page = SHEET["cols"] * SHEET["rows"]
        page_h = letter[1]
        for i, code in enumerate(codes):
            if i and i % per_page == 0:
                c.showPage()
            slot = i % per_page
            row, col = divmod(slot, SHEET["cols"])
            x = SHEET["left"] + col * SHEET["col_pitch"]
            y = page_h - SHEET["top"] - (row + 1) * SHEET["height"]
            _draw_label(c, x, y, SHEET["width"], SHEET["height"], code, base_url)
        c.showPage()
    c.save()
    buf.seek(0)
    return buf
