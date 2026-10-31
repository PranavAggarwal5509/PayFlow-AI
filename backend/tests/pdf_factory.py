"""Generate small valid PDFs for tests (digital text, scanned image, corrupted)."""

import io
import random

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make_pdf(text: str, *, salt: str | None = None) -> bytes:
    """A one-page digital PDF. `salt` makes the bytes unique without changing the visible text."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, invariant=True)
    pdf.setTitle(salt or "invoice")
    y = 800
    for line in _wrap(text, 90):
        pdf.drawString(40, y, line)
        y -= 14
        if y < 40:
            break
    pdf.save()
    return buffer.getvalue()


def make_image_only_pdf() -> bytes:
    """A PDF containing only a drawn rectangle: no text layer → triggers the OCR path."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, invariant=True)
    pdf.rect(50, 50, 200, 100, fill=1)
    pdf.save()
    return buffer.getvalue()


def make_corrupted_pdf() -> bytes:
    rng = random.Random(7)
    return b"%PDF-1.4\n" + bytes(rng.randrange(256) for _ in range(512))


def _wrap(text: str, width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    return [*lines, current] if current else lines

