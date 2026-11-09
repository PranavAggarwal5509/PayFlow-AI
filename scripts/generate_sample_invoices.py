"""Render the PayFlow AI dataset: realistic Indian GST tax invoices + master-data JSON.

Usage (from repo root):  python scripts/generate_sample_invoices.py

Three real-world templates (each vendor always uses the same one, like a real billing system):
* tally      - boxed Tally-style tax invoice with an e-invoice IRN / Ack No. / signed QR block
* corporate  - branded ERP layout (Zoho / SAP style) with Bill-to / Ship-to cards
* services   - letterhead invoice for service providers (SAC codes, service period)

Every invoice carries what GST Rule 46 requires: supplier GSTIN + state code, invoice number and
date, recipient GSTIN, place of supply, HSN/SAC per line, taxable value, CGST+SGST or IGST
breakdown, round-off, total in words, bank details and an authorised signatory.

Outputs: sample_data/{invoices,invoices/history,vendors,purchase_orders} and the frontend scenario
list (frontend/public/samples/*.pdf + frontend/lib/samples.ts).
"""

import hashlib
import io
import json
import math
import random
import shutil
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pymupdf
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).parent))
from sample_catalog import (  # noqa: E402
    BUYER,
    HISTORY,
    INVOICES,
    PO_BY_NUMBER,
    POS,
    STATES,
    VENDOR_BY_CODE,
    VENDOR_INFO,
    Spec,
    item_meta,
    po_total,
    vendor_bank,
    vendor_bank_branch,
)

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "sample_data"
FRONTEND = REPO / "frontend"
W, H = A4
INK = colors.HexColor("#111827")
GREY = colors.HexColor("#4b5563")
LIGHT = colors.HexColor("#9ca3af")


# ------------------------------------------------------------------ fonts
def _register_fonts() -> tuple[str, str, str]:
    """Arial carries the ₹ glyph; fall back to Helvetica + 'Rs.' elsewhere."""
    candidates = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/msttcorefonts"), Path("/Library/Fonts")]
    for folder in candidates:
        regular, bold, italic = folder / "arial.ttf", folder / "arialbd.ttf", folder / "ariali.ttf"
        if regular.exists() and bold.exists() and italic.exists():
            pdfmetrics.registerFont(TTFont("Sans", str(regular)))
            pdfmetrics.registerFont(TTFont("Sans-Bold", str(bold)))
            pdfmetrics.registerFont(TTFont("Sans-Italic", str(italic)))
            return "Sans", "Sans-Bold", "Sans-Italic"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


F, FB, FI = _register_fonts()
RUPEE = "₹" if F == "Sans" else "Rs."


# ------------------------------------------------------------------ formatting
def inr(value: Decimal | float | int) -> str:
    """Indian digit grouping: 1234567.5 -> 12,34,567.50"""
    q = Decimal(str(value)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    sign = "-" if q < 0 else ""
    whole, frac = f"{abs(q):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}{whole}.{frac}"


_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
         "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]  # fmt: skip
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _below_thousand(n: int) -> str:
    parts = []
    if n >= 100:
        parts.append(f"{_ONES[n // 100]} Hundred")
        n %= 100
    if n >= 20:
        parts.append(_TENS[n // 10] + (f" {_ONES[n % 10]}" if n % 10 else ""))
    elif n:
        parts.append(_ONES[n])
    return " ".join(parts)


def words(value: Decimal) -> str:
    """Indian numbering in words: 114460 -> 'One Lakh Fourteen Thousand Four Hundred Sixty'."""
    q = Decimal(str(value)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    rupees, paise = int(q), int((q - int(q)) * 100)
    out, n = [], rupees
    for size, name in ((10**7, "Crore"), (10**5, "Lakh"), (1000, "Thousand")):
        if n >= size:
            out.append(f"{_below_thousand(n // size)} {name}")
            n %= size
    if n:
        out.append(_below_thousand(n))
    text = " ".join(out) or "Zero"
    if paise:
        text += f" and {_below_thousand(paise)} paise"
    return f"INR {text} Only"


def d_tally(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d-%b-%Y") if iso else ""


def d_slash(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else ""


def d_long(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d %b %Y") if iso else ""


def qty_text(q) -> str:
    return f"{Decimal(str(q)):,.0f}" if Decimal(str(q)) == int(q) else f"{q}"


# ------------------------------------------------------------------ shared pieces
class Doc:
    """Everything a template needs, derived once from a Spec."""

    def __init__(self, spec: Spec):
        self.spec = spec
        self.vendor = VENDOR_BY_CODE[spec.vendor_code]
        self.po_row = PO_BY_NUMBER.get(spec.po or "")
        self.subtotal, self.tax, self.total = spec.amounts()
        self.round_off = spec.round_off()
        self.tax_lines = spec.tax_lines()
        self.intra = spec.intra_state
        self.state_name = STATES[self.vendor.state]
        bank = spec.bank or vendor_bank(self.vendor.code)
        self.bank_name, self.account, self.ifsc = bank
        self.branch = vendor_bank_branch(self.vendor.code) if spec.bank in (None, vendor_bank(self.vendor.code)) else "Sector 18 Branch"
        seed = f"{self.vendor.gstin}|{spec.number}|{spec.date}"
        self.irn = hashlib.sha256(seed.encode()).hexdigest()
        self.ack_no = str(int(hashlib.md5(seed.encode()).hexdigest()[:12], 16))[:15].rjust(15, "1")
        self.rng = random.Random(seed)

    @property
    def gstin_text(self) -> str:
        return self.spec.gstin or ""

    def hsn_rows(self) -> list[tuple[str, Decimal, int, Decimal]]:
        """[(HSN, taxable, rate, tax)] — the HSN-wise summary GST requires."""
        rows: dict[tuple[str, int], Decimal] = {}
        for desc, qty, price, rate in self.spec.items:
            key = (item_meta(desc)[0], rate)
            rows[key] = rows.get(key, Decimal("0")) + Decimal(str(price)) * qty
        out = []
        for (hsn, rate), taxable in rows.items():
            if self.intra:
                half = (taxable * Decimal(rate) / 200).quantize(Decimal("0.01"), ROUND_HALF_UP)
                out.append((hsn, taxable, rate, half * 2))
            else:
                out.append((hsn, taxable, rate, (taxable * Decimal(rate) / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)))
        return out


def text(c, x, y, s, size=8, font=None, color=INK, align="left"):
    c.setFont(font or F, size)
    c.setFillColor(color)
    {"left": c.drawString, "right": c.drawRightString, "center": c.drawCentredString}[align](x, y, s)


def wrap(s: str, width: float, size: float, font=None) -> list[str]:
    font = font or F
    lines, line = [], ""
    for word in s.split():
        trial = f"{line} {word}".strip()
        if pdfmetrics.stringWidth(trial, font, size) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def qr(c, value: str, x: float, y: float, size: float):
    widget = QrCodeWidget(value)
    x0, y0, x1, y1 = widget.getBounds()
    drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, c, x, y)


def seal(c, cx: float, cy: float, name: str, city: str, color="#1d4ed8", r=34):
    """Round rubber-stamp company seal with curved text."""
    col = colors.HexColor(color)
    c.saveState()
    c.translate(cx, cy)
    c.rotate(-12)
    c.setStrokeColor(col)
    c.setFillColor(col)
    c.setStrokeAlpha(0.75)
    c.setFillAlpha(0.75)
    c.setLineWidth(1.6)
    c.circle(0, 0, r, stroke=1, fill=0)
    c.setLineWidth(0.7)
    c.circle(0, 0, r - 11, stroke=1, fill=0)
    label = name.upper().replace(" PVT LTD", " PVT. LTD.")
    size = 5.6 if len(label) < 30 else 4.8
    c.setFont(FB, size)
    span = 250
    step = span / max(len(label), 1)
    for i, ch in enumerate(label):
        angle = 90 + span / 2 - step * (i + 0.5)
        c.saveState()
        c.rotate(angle)
        c.translate(r - 8, 0)
        c.rotate(-90)
        c.drawCentredString(0, 0, ch)
        c.restoreState()
    c.setFont(FB, 5.2)
    c.drawCentredString(0, 2, city.upper())
    c.setFont(F, 4.5)
    c.drawCentredString(0, -6, "AUTHORISED")
    c.restoreState()


def signature(c, x: float, y: float, rng: random.Random):
    """A quick pen scribble above the 'Authorised Signatory' line."""
    c.saveState()
    c.setStrokeColor(colors.HexColor("#1e3a8a"))
    c.setLineWidth(0.9)
    p = c.beginPath()
    p.moveTo(x, y)
    px = x
    for _ in range(5):
        dx = rng.uniform(8, 14)
        p.curveTo(px + dx * 0.3, y + rng.uniform(6, 13), px + dx * 0.7, y - rng.uniform(4, 9), px + dx, y + rng.uniform(-2, 3))
        px += dx
    p.curveTo(px + 6, y + 10, px - 30, y - 6, px + 18, y + 1)
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()


def stamp_label(c, label: str, x: float, y: float):
    c.saveState()
    c.translate(x, y)
    c.rotate(8)
    red = colors.HexColor("#b91c1c")
    c.setStrokeColor(red)
    c.setFillColor(red)
    c.setLineWidth(1.4)
    width = pdfmetrics.stringWidth(label, FB, 11) + 16
    c.roundRect(-width / 2, -9, width, 20, 3, stroke=1, fill=0)
    c.setFont(FB, 11)
    c.drawCentredString(0, -3, label)
    c.restoreState()


def tax_label(rate: int, intra: bool) -> list[tuple[str, Decimal]]:
    half = Decimal(rate) / 2
    return [(f"CGST @ {half.normalize():f}%", half), (f"SGST @ {half.normalize():f}%", half)] if intra else [(f"IGST @ {rate}%", Decimal(rate))]


def tax_split(doc: Doc) -> list[tuple[str, Decimal]]:
    """[('CGST @ 9%', 8730.00), ...] in print order."""
    out = []
    for rate, _, tax in doc.tax_lines:
        parts = tax_label(rate, doc.intra)
        if len(parts) == 2:
            out += [(parts[0][0], tax / 2), (parts[1][0], tax / 2)]
        else:
            out.append((parts[0][0], tax))
    return out


# ------------------------------------------------------------------ template 1: Tally-style e-invoice
def tally(c, doc: Doc):
    s, v = doc.spec, doc.vendor
    X0, X1 = 24, W - 24
    MID = X0 + 270
    c.setLineWidth(0.6)
    c.setStrokeColor(INK)

    text(c, W / 2, H - 30, "Tax Invoice", 12, FB, align="center")
    text(c, X1, H - 30, "(ORIGINAL FOR RECIPIENT)", 7, FI, GREY, align="right")
    if s.label:
        stamp_label(c, s.label, X1 - 70, H - 58)

    # e-invoice block
    top = H - 40
    text(c, X0, top - 12, "IRN", 7.5, FB)
    text(c, X0 + 52, top - 12, f": {doc.irn}", 7.2)
    text(c, X0, top - 24, "Ack No.", 7.5, FB)
    text(c, X0 + 52, top - 24, f": {doc.ack_no}", 7.5)
    text(c, X0, top - 36, "Ack Date", 7.5, FB)
    text(c, X0 + 52, top - 36, f": {d_tally(s.date)}", 7.5)
    text(c, X1 - 36, top - 2, "e-Invoice", 7, FB, align="center")
    qr(c, f"{v.gstin}|{BUYER['gstin']}|{s.number}|{s.date}|{doc.total}|{doc.irn[:24]}", X1 - 72, top - 76, 72)

    y = H - 120
    c.rect(X0, 60, X1 - X0, y - 60)  # outer frame

    # supplier + meta grid
    block = 96
    c.line(MID, y, MID, y - block)
    text(c, X0 + 5, y - 13, v.name, 10, FB)
    yy = y - 25
    for line in v.address:
        text(c, X0 + 5, yy, line, 7.8)
        yy -= 10
    text(c, X0 + 5, yy, f"GSTIN/UIN: {doc.gstin_text}" if s.gstin else "GSTIN/UIN:", 7.8)
    text(c, X0 + 5, yy - 10, f"State Name : {doc.state_name}, Code : {v.state}", 7.8)
    text(c, X0 + 5, yy - 20, f"E-Mail : {v.email}", 7.8)
    cells = [
        ("Invoice No.", s.number or "", "Dated", d_tally(s.date)),
        ("Delivery Note", f"DN/{(s.number or 'X')[-4:]}", "Mode/Terms of Payment", "30 Days"),
        ("Reference No. & Date.", "", "Other References", s.note[:34] if s.note else ""),
        ("Buyer's Order No.", s.po or "", "Dated", d_tally(doc.po_row[2]) if doc.po_row else ""),
    ]
    cw = (X1 - MID) / 2
    for i, (l1, v1, l2, v2) in enumerate(cells):
        ty = y - i * block / 4
        if i:
            c.line(MID, ty, X1, ty)
        c.line(MID + cw, ty, MID + cw, ty - block / 4)
        text(c, MID + 4, ty - 9, l1, 6.8, color=GREY)
        text(c, MID + 4, ty - 19, v1, 8, FB)
        text(c, MID + cw + 4, ty - 9, l2, 6.8, color=GREY)
        text(c, MID + cw + 4, ty - 19, v2, 8, FB)
    y -= block
    c.line(X0, y, X1, y)

    # consignee / buyer + dispatch grid
    block = 128
    c.line(MID, y, MID, y - block)
    text(c, X0 + 5, y - 10, "Consignee (Ship to)", 6.8, color=GREY)
    text(c, X0 + 5, y - 21, BUYER["ship_to"][0], 8, FB)
    for i, line in enumerate(BUYER["ship_to"][1:]):
        text(c, X0 + 5, y - 31 - i * 9.5, line, 7.6)
    text(c, X0 + 5, y - 50, f"GSTIN/UIN    : {BUYER['gstin']}", 7.6)
    c.line(X0, y - 58, MID, y - 58)
    text(c, X0 + 5, y - 68, "Buyer (Bill to)", 6.8, color=GREY)
    text(c, X0 + 5, y - 79, BUYER["name"], 8, FB)
    for i, line in enumerate(BUYER["address"]):
        text(c, X0 + 5, y - 89 - i * 9.5, line, 7.6)
    text(c, X0 + 5, y - 122, f"GSTIN/UIN : {BUYER['gstin']}    State Name : Maharashtra, Code : 27", 7.2)
    cells = [
        ("Dispatch Doc No.", f"LR-{doc.rng.randint(10000, 99999)}", "Delivery Note Date", d_tally(s.date)),
        ("Dispatched through", "By Road" if s.items and item_meta(s.items[0][0])[0][:2] not in ("99",) else "-", "Destination", "Bhiwandi"),
    ]
    for i, (l1, v1, l2, v2) in enumerate(cells):
        ty = y - i * 29
        if i:
            c.line(MID, ty, X1, ty)
        c.line(MID + cw, ty, MID + cw, ty - 29)
        text(c, MID + 4, ty - 9, l1, 6.8, color=GREY)
        text(c, MID + 4, ty - 20, v1, 8, FB)
        text(c, MID + cw + 4, ty - 9, l2, 6.8, color=GREY)
        text(c, MID + cw + 4, ty - 20, v2, 8, FB)
    ty = y - 58
    c.line(MID, ty, X1, ty)
    text(c, MID + 4, ty - 9, "Terms of Delivery", 6.8, color=GREY)
    text(c, MID + 4, ty - 21, f"Payment Due Date : {d_tally(s.due)}", 8, FB)
    text(c, MID + 4, ty - 33, f"Place of Supply : Maharashtra (27)", 8)
    text(c, MID + 4, ty - 45, "Reverse Charge : No", 8)
    y -= block
    c.line(X0, y, X1, y)

    # item table
    cols = [X0, X0 + 26, X0 + 236, X0 + 300, X0 + 362, X0 + 424, X0 + 452, X1]
    heads = ["Sl\nNo.", "Description of Goods / Services", "HSN/SAC", "Quantity", "Rate", "per", "Amount"]
    text_y = y - 14
    for i, h_ in enumerate(heads):
        lines = h_.split("\n")
        for j, ln in enumerate(lines):
            text(c, (cols[i] + cols[i + 1]) / 2, text_y - j * 8 + (4 if len(lines) > 1 else 0), ln, 7.2, FB, align="center")
    y -= 22
    c.line(X0, y, X1, y)
    table_top = y
    y -= 14
    for n, (desc, qty, price, _rate) in enumerate(s.items, start=1):
        hsn, unit, _ = item_meta(desc)
        text(c, cols[0] + 13, y, str(n), 8, align="center")
        text(c, cols[1] + 4, y, desc, 8.4, FB)
        text(c, cols[2] + 4, y, hsn, 8)
        text(c, cols[4] - 4, y, f"{qty_text(qty)} {unit}", 8, FB, align="right")
        text(c, cols[5] - 4, y, inr(price), 8, align="right")
        text(c, cols[5] + 4, y, unit, 7.5)
        text(c, X1 - 4, y, inr(Decimal(str(price)) * qty), 8, FB, align="right")
        y -= 16
    if s.note:
        text(c, cols[1] + 10, y + 4, s.note, 7.2, FI, GREY)
        y -= 10
    c.line(cols[6], y + 6, X1, y + 6)
    text(c, X1 - 4, y - 4, inr(doc.subtotal), 8, align="right")
    y -= 18
    for label, amount in tax_split(doc):
        text(c, cols[2] - 6, y, label, 8, FB, align="right")
        text(c, X1 - 4, y, inr(amount), 8, FB, align="right")
        y -= 13
    if doc.round_off:
        text(c, cols[2] - 6, y, "Round Off", 8, FI, align="right")
        text(c, X1 - 4, y, ("(-)" if doc.round_off < 0 else "") + inr(abs(doc.round_off)), 8, align="right")
        y -= 13
    y = min(y, table_top - 190)
    for x in cols[1:-1]:
        c.line(x, table_top + 22, x, y)
    c.line(X0, y, X1, y)
    text(c, cols[2] - 6, y - 12, "Total", 8.5, FB, align="right")
    text(c, X1 - 4, y - 12, f"{RUPEE} {inr(doc.total)}", 9.5, FB, align="right")
    y -= 18
    c.line(X0, y, X1, y)

    text(c, X0 + 5, y - 10, "Amount Chargeable (in words)", 6.8, color=GREY)
    text(c, X1 - 5, y - 10, "E. & O.E", 6.8, FI, GREY, align="right")
    text(c, X0 + 5, y - 22, words(doc.total), 8.4, FB)
    y -= 30
    c.line(X0, y, X1, y)

    # HSN summary
    if doc.intra:
        hcols = [X0, X0 + 120, X0 + 220, X0 + 268, X0 + 340, X0 + 388, X0 + 460, X1]
        heads = ["HSN/SAC", "Taxable Value", "CGST Rate", "CGST Amount", "SGST Rate", "SGST Amount", "Total Tax"]
    else:
        hcols = [X0, X0 + 150, X0 + 270, X0 + 340, X0 + 440, X1]
        heads = ["HSN/SAC", "Taxable Value", "IGST Rate", "IGST Amount", "Total Tax Amount"]
    for i, h_ in enumerate(heads):
        text(c, (hcols[i] + hcols[i + 1]) / 2, y - 10, h_, 6.8, FB, align="center")
    hy = y - 14
    c.line(X0, hy, X1, hy)
    rows = doc.hsn_rows()
    for hsn, taxable, rate, tax in rows:
        hy -= 11
        vals = [hsn, inr(taxable)]
        if doc.intra:
            vals += [f"{Decimal(rate) / 2:g}%", inr(tax / 2), f"{Decimal(rate) / 2:g}%", inr(tax / 2), inr(tax)]
        else:
            vals += [f"{rate}%", inr(tax), inr(tax)]
        for i, val in enumerate(vals):
            if i == 0:
                text(c, hcols[0] + 4, hy, val, 7.6)
            else:
                text(c, hcols[i + 1] - 4, hy, val, 7.6, align="right")
    hy -= 5
    c.line(X0, hy, X1, hy)
    hy -= 10
    text(c, hcols[1] - 4, hy, "Total", 7.6, FB, align="right")
    text(c, hcols[2] - 4, hy, inr(doc.subtotal), 7.6, FB, align="right")
    text(c, X1 - 4, hy, inr(doc.tax), 7.6, FB, align="right")
    for x in hcols[1:-1]:
        c.line(x, y, x, hy - 4)
    hy -= 4
    c.line(X0, hy, X1, hy)
    text(c, X0 + 5, hy - 12, f"Tax Amount (in words) :  {words(doc.tax)}", 7.8, FB)
    y = hy - 20

    # footer blocks
    text(c, X0 + 5, y - 6, f"Company's PAN      :  {v.pan}", 7.8, FB)
    text(c, X0 + 5, y - 22, "Declaration", 7, FB)
    for i, line in enumerate(wrap("We declare that this invoice shows the actual price of the goods described and that all particulars are true and correct.", 250, 7)):
        text(c, X0 + 5, y - 32 - i * 9, line, 7)
    text(c, MID + 4, y - 6, "Company's Bank Details", 7, FB)
    text(c, MID + 4, y - 17, f"Bank Name            :  {doc.bank_name}", 7.6)
    text(c, MID + 4, y - 27, f"A/c No.                  :  {doc.account}", 7.6, FB)
    text(c, MID + 4, y - 37, f"Branch & IFS Code :  {doc.branch} & {doc.ifsc}", 7.6)
    sig_top = y - 44
    c.rect(MID, 60, X1 - MID, sig_top - 60)
    text(c, X1 - 6, sig_top - 11, f"for {v.name}", 8, FB, align="right")
    seal(c, MID + 62, min(100, sig_top - 40), v.name, v.city)
    signature(c, X1 - 120, 86, doc.rng)
    text(c, X1 - 6, 66, "Authorised Signatory", 7.6, align="right")
    text(c, W / 2, 46, f"SUBJECT TO {v.city.upper()} JURISDICTION", 7, FB, align="center")
    text(c, W / 2, 36, "This is a Computer Generated Invoice", 6.8, color=GREY, align="center")


# ------------------------------------------------------------------ template 2: corporate ERP
def corporate(c, doc: Doc):
    s, v = doc.spec, doc.vendor
    accent = colors.HexColor(v.accent)
    soft = colors.Color(accent.red, accent.green, accent.blue, alpha=0.08)
    X0, X1 = 36, W - 36

    c.setFillColor(accent)
    c.rect(0, H - 104, W, 104, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.roundRect(X0, H - 82, 46, 46, 8, fill=1, stroke=0)
    initials = "".join(w[0] for w in v.name.split()[:2]).upper()
    text(c, X0 + 23, H - 66, initials, 17, FB, accent, align="center")
    text(c, X0 + 58, H - 50, v.name, 15, FB, colors.white)
    text(c, X0 + 58, H - 63, v.one_line_address, 7.8, color=colors.white)
    text(c, X0 + 58, H - 75, f"GSTIN: {doc.gstin_text}   |   PAN: {v.pan}   |   {v.email}   |   {v.phone}" if s.gstin else f"PAN: {v.pan}   |   {v.email}   |   {v.phone}", 7.4, color=colors.white)
    text(c, X1, H - 48, "TAX INVOICE", 17, FB, colors.white, align="right")
    text(c, X1, H - 60, "Original for Recipient", 7, FI, colors.white, align="right")
    if s.label:
        stamp_label(c, s.label, X1 - 60, H - 128)

    y = H - 126
    card_w = (X1 - X0 - 20) / 3
    blocks = [
        ("BILL TO", [BUYER["name"], *BUYER["address"], f"GSTIN: {BUYER['gstin']}", "State: Maharashtra (27)"]),
        ("SHIP TO", [*BUYER["ship_to"], "State: Maharashtra (27)"]),
    ]
    for i, (title, lines) in enumerate(blocks):
        x = X0 + i * (card_w + 10)
        text(c, x, y, title, 7, FB, accent)
        wrapped = [(seg, j == 0) for j, line in enumerate(lines) for seg in wrap(line, card_w - 8, 7.6, FB if j == 0 else F)]
        for j, (line, bold) in enumerate(wrapped):
            text(c, x, y - 13 - j * 10, line, 7.6, FB if bold else F)
    x = X0 + 2 * (card_w + 10)
    meta = [
        ("Invoice #", s.number or "-"),
        ("Invoice Date", d_long(s.date)),
        ("Due Date", d_long(s.due)),
        ("PO Number", s.po or "-"),
        ("PO Date", d_long(doc.po_row[2]) if doc.po_row else "-"),
        ("Place of Supply", "Maharashtra (27)"),
        ("Reverse Charge", "No"),
    ]
    c.setFillColor(soft)
    c.roundRect(x - 6, y - 80, card_w + 12, 92, 6, fill=1, stroke=0)
    for j, (label, value) in enumerate(meta):
        text(c, x, y - j * 11.5, label, 7.4, color=GREY)
        text(c, X1, y - j * 11.5, value, 7.6, FB, align="right")

    y -= 106
    cols = [X0, X0 + 22, X0 + 214, X0 + 270, X0 + 316, X0 + 384, X0 + 424, X1]
    heads = ["#", "Item & Description", "HSN/SAC", "Qty", "Rate", "GST", "Taxable Value"]
    c.setFillColor(accent)
    c.rect(X0, y - 6, X1 - X0, 20, fill=1, stroke=0)
    for i, h_ in enumerate(heads):
        if i in (0, 1, 2):
            text(c, cols[i] + 5, y, h_, 7.6, FB, colors.white)
        else:
            text(c, cols[i + 1] - 5, y, h_, 7.6, FB, colors.white, align="right")
    y -= 22
    for n, (desc, qty, price, rate) in enumerate(s.items, start=1):
        hsn, unit, _ = item_meta(desc)
        if n % 2 == 0:
            c.setFillColor(soft)
            c.rect(X0, y - 9, X1 - X0, 24, fill=1, stroke=0)
        text(c, cols[0] + 5, y, str(n), 8)
        text(c, cols[1] + 5, y, desc, 8.4, FB)
        text(c, cols[1] + 5, y - 9, f"Unit: {unit}", 6.6, color=GREY)
        text(c, cols[2] + 5, y, hsn, 8)
        text(c, cols[4] - 5, y, qty_text(qty), 8, align="right")
        text(c, cols[5] - 5, y, inr(price), 8, align="right")
        text(c, cols[6] - 5, y, f"{rate}%", 8, align="right")
        text(c, X1 - 5, y, inr(Decimal(str(price)) * qty), 8, FB, align="right")
        y -= 24
    if s.note:
        text(c, cols[1] + 5, y + 6, s.note, 7.2, FI, GREY)
        y -= 10
    c.setStrokeColor(colors.HexColor("#e5e7eb"))
    c.line(X0, y + 8, X1, y + 8)

    # totals
    ty = y - 10
    tx = X0 + 330
    rows = [("Taxable Amount", inr(doc.subtotal))]
    for rate, taxable, tax in doc.tax_lines:
        for label, _ in tax_label(rate, doc.intra):
            amount = tax / 2 if doc.intra else tax
            rows.append((f"{label.split(' @ ')[0]} ({label.split(' @ ')[1]}) on {inr(taxable)}", inr(amount)))
    if doc.round_off:
        rows.append(("Round Off", ("-" if doc.round_off < 0 else "+") + inr(abs(doc.round_off))))
    for label, value in rows:
        text(c, tx, ty, label, 7.8, color=GREY)
        text(c, X1 - 5, ty, value, 8, align="right")
        ty -= 13
    c.setFillColor(accent)
    c.roundRect(tx - 6, ty - 10, X1 - tx + 6, 22, 4, fill=1, stroke=0)
    text(c, tx, ty - 3, f"Total ({RUPEE})", 9.5, FB, colors.white)
    text(c, X1 - 6, ty - 3, inr(doc.total), 10.5, FB, colors.white, align="right")
    text(c, tx, ty - 24, "Total GST", 7.4, color=GREY)
    text(c, X1 - 5, ty - 24, inr(doc.tax), 7.6, align="right")

    # left column: words, bank, terms
    ly = y - 10
    text(c, X0, ly, "Total in words", 7, FB, accent)
    for i, line in enumerate(wrap(words(doc.total), 270, 8, FB)):
        text(c, X0, ly - 12 - i * 10, line, 8, FB)
    ly -= 46
    c.setStrokeColor(colors.HexColor("#d1d5db"))
    c.roundRect(X0, ly - 58, 280, 66, 5, stroke=1, fill=0)
    text(c, X0 + 8, ly - 4, "BANK DETAILS FOR NEFT / RTGS", 7, FB, accent)
    for i, (label, value) in enumerate([("Account Name", v.name), ("Bank", doc.bank_name), ("Account No.", doc.account), ("IFSC", f"{doc.ifsc}  ({doc.branch})")]):
        text(c, X0 + 8, ly - 17 - i * 11, label, 7.4, color=GREY)
        text(c, X0 + 72, ly - 17 - i * 11, value, 7.6, FB)
    ly -= 74
    text(c, X0, ly, "Terms & Conditions", 7, FB, accent)
    terms = [
        "1. Payment within 30 days of invoice date. Interest @ 18% p.a. on overdue amounts.",
        "2. Goods once sold will not be taken back. Subject to " + v.city + " jurisdiction.",
        "3. Please quote the invoice number on all payments and correspondence.",
    ]
    for i, t in enumerate(terms):
        text(c, X0, ly - 11 - i * 9.5, t, 6.9, color=GREY)

    sy = min(ty - 50, ly - 40)
    sy = max(sy, 120)
    text(c, X1, sy, f"For {v.name}", 8, FB, align="right")
    seal(c, X1 - 150, sy - 38, v.name, v.city, color=v.accent)
    signature(c, X1 - 100, sy - 30, doc.rng)
    c.setStrokeColor(GREY)
    c.line(X1 - 120, sy - 46, X1, sy - 46)
    text(c, X1, sy - 56, "Authorised Signatory", 7.4, align="right")

    c.setFillColor(soft)
    c.rect(0, 0, W, 34, fill=1, stroke=0)
    text(c, W / 2, 20, f"{v.name}  ·  {v.email}  ·  {v.phone}", 7, color=GREY, align="center")
    text(c, W / 2, 10, "This is a computer-generated invoice and does not require a physical signature.", 6.6, FI, LIGHT, align="center")


# ------------------------------------------------------------------ template 3: services letterhead
def services(c, doc: Doc):
    s, v = doc.spec, doc.vendor
    accent = colors.HexColor(v.accent)
    X0, X1 = 42, W - 42

    text(c, W / 2, H - 52, v.name.upper(), 18, "Times-Bold", accent, align="center")
    text(c, W / 2, H - 66, v.one_line_address, 8, color=GREY, align="center")
    text(c, W / 2, H - 77, f"Tel: {v.phone}   |   E-mail: {v.email}", 7.6, color=GREY, align="center")
    c.setStrokeColor(accent)
    c.setLineWidth(1.6)
    c.line(X0, H - 86, X1, H - 86)
    c.setLineWidth(0.5)
    c.line(X0, H - 89, X1, H - 89)
    text(c, W / 2, H - 108, "T A X   I N V O I C E", 12, FB, INK, align="center")
    if s.label:
        stamp_label(c, s.label, X1 - 60, H - 108)

    y = H - 124
    c.setStrokeColor(colors.HexColor("#9ca3af"))
    c.setLineWidth(0.5)
    left = [
        ("Invoice No.", s.number or ""),
        ("Invoice Date", d_slash(s.date)),
        ("Due Date", d_slash(s.due)),
        ("Supplier GSTIN", doc.gstin_text),
        ("Supplier PAN", v.pan),
    ]
    right = [
        ("Client PO No.", s.po or ""),
        ("PO Date", d_slash(doc.po_row[2]) if doc.po_row else ""),
        ("Place of Supply", "Maharashtra (27)"),
        ("State of Supplier", f"{doc.state_name} ({v.state})"),
        ("Reverse Charge", "No"),
    ]
    mid = (X0 + X1) / 2
    rh = 15
    c.rect(X0, y - rh * len(left), X1 - X0, rh * len(left))
    c.line(mid, y, mid, y - rh * len(left))
    for i, ((l1, v1), (l2, v2)) in enumerate(zip(left, right)):
        ry = y - (i + 1) * rh
        if i:
            c.line(X0, ry + rh, X1, ry + rh)
        text(c, X0 + 5, ry + 4.5, l1, 7.6, color=GREY)
        text(c, X0 + 92, ry + 4.5, f": {v1}", 7.8, FB)
        text(c, mid + 5, ry + 4.5, l2, 7.6, color=GREY)
        text(c, mid + 92, ry + 4.5, f": {v2}", 7.8, FB)
    y -= rh * len(left) + 18

    text(c, X0, y, "Bill To:", 7.6, FB, accent)
    text(c, X0, y - 12, BUYER["name"], 9, FB)
    for i, line in enumerate(BUYER["address"]):
        text(c, X0, y - 23 - i * 10, line, 7.8)
    text(c, X0, y - 54, f"GSTIN: {BUYER['gstin']}    State Code: 27", 7.8, FB)
    if s.note:
        text(c, mid + 10, y, "Particulars:", 7.6, FB, accent)
        for i, line in enumerate(wrap(s.note, X1 - mid - 10, 8)):
            text(c, mid + 10, y - 12 - i * 10, line, 8)
    y -= 72

    cols = [X0, X0 + 30, X0 + 262, X0 + 316, X0 + 366, X0 + 430, X1]
    heads = ["S.No", "Description of Services", "SAC", "Qty", "Rate", "Amount"]
    c.setFillColor(colors.HexColor("#f3f4f6"))
    c.rect(X0, y - 18, X1 - X0, 18, fill=1, stroke=1)
    for i, h_ in enumerate(heads):
        text(c, (cols[i] + cols[i + 1]) / 2, y - 12, h_, 7.6, FB, align="center")
    top = y
    y -= 32
    for n, (desc, qty, price, _rate) in enumerate(s.items, start=1):
        hsn, unit, _ = item_meta(desc)
        text(c, (cols[0] + cols[1]) / 2, y, str(n), 8, align="center")
        text(c, cols[1] + 5, y, desc, 8.2)
        text(c, (cols[2] + cols[3]) / 2, y, hsn, 8, align="center")
        text(c, cols[4] - 5, y, qty_text(qty), 8, align="right")
        text(c, cols[5] - 5, y, inr(price), 8, align="right")
        text(c, X1 - 5, y, inr(Decimal(str(price)) * qty), 8, align="right")
        y -= 17
    bottom = min(y, top - 120)
    c.rect(X0, bottom, X1 - X0, top - 18 - bottom)
    for x in cols[1:-1]:
        c.line(x, top, x, bottom)
    y = bottom

    # tax computation box
    rows = [("Taxable Value", inr(doc.subtotal))]
    for label, amount in tax_split(doc):
        rows.append((label, inr(amount)))
    if doc.round_off:
        rows.append(("Round off", ("(-) " if doc.round_off < 0 else "") + inr(abs(doc.round_off))))
    bx = cols[4]
    for label, value in rows:
        y -= 14
        c.rect(bx, y - 4, X1 - bx, 14)
        text(c, bx + 5, y + 0.5, label, 7.8)
        text(c, X1 - 5, y + 0.5, value, 8, align="right")
    y -= 18
    c.setFillColor(accent)
    c.rect(bx, y - 4, X1 - bx, 18, fill=1, stroke=0)
    text(c, bx + 5, y + 1.5, "Invoice Total", 8.5, FB, colors.white)
    text(c, X1 - 5, y + 1.5, f"{RUPEE} {inr(doc.total)}", 9, FB, colors.white, align="right")
    text(c, X0, bottom - 16, "Amount in words:", 7.4, FB, accent)
    for i, line in enumerate(wrap(words(doc.total), bx - X0 - 12, 8, FB)):
        text(c, X0, bottom - 28 - i * 10, line, 8, FB)
    text(c, X0, bottom - 58, f"Total GST (in words): {words(doc.tax)}", 7, color=GREY)
    y -= 26

    c.setStrokeColor(accent)
    c.roundRect(X0, y - 64, 270, 70, 4, stroke=1, fill=0)
    text(c, X0 + 8, y - 6, "Bank Details", 8, FB, accent)
    for i, (label, value) in enumerate([("Beneficiary", v.name), ("Bank Name", doc.bank_name), ("Account No.", doc.account), ("IFSC Code", doc.ifsc), ("Branch", doc.branch)]):
        text(c, X0 + 8, y - 19 - i * 10, label, 7.4, color=GREY)
        text(c, X0 + 70, y - 19 - i * 10, f": {value}", 7.6, FB)
    text(c, X0, y - 80, "Payment Terms: Within 30 days of invoice date. TDS, if applicable, to be deducted u/s 194C / 194J.", 6.9, color=GREY)
    text(c, X0, y - 90, "Interest @ 18% p.a. will be charged on payments received after the due date.", 6.9, color=GREY)

    text(c, X1, y - 6, f"For {v.name}", 8, FB, align="right")
    seal(c, X1 - 150, y - 46, v.name, v.city, color=v.accent)
    signature(c, X1 - 96, y - 40, doc.rng)
    text(c, X1, y - 66, "Authorised Signatory", 7.6, align="right")

    c.setStrokeColor(accent)
    c.line(X0, 42, X1, 42)
    cin = f"U{74999 + int(v.code[-2:])}MH2016PTC{280000 + int(v.code[-4:])}"
    tail = f"   |   CIN: {cin}" if "Pvt Ltd" in v.name else ""
    text(c, W / 2, 30, f"GSTIN: {doc.gstin_text or '-'}   |   PAN: {v.pan}{tail}", 7, color=GREY, align="center")
    text(c, W / 2, 20, "This is a computer generated invoice.", 6.6, FI, LIGHT, align="center")


TEMPLATES = {"tally": tally, "corporate": corporate, "services": services}


def draw(spec: Spec) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4, invariant=True)
    c.setTitle(f"Tax Invoice {spec.number or ''}".strip())
    c.setAuthor(VENDOR_BY_CODE[spec.vendor_code].name)
    c.setCreator("Billing system")
    TEMPLATES[spec.layout](c, Doc(spec))
    c.showPage()
    c.save()
    return buffer.getvalue()


# ------------------------------------------------------------------ scans & corruption
def make_scanned(pdf_bytes: bytes, seed: int = 1) -> bytes:
    """Photocopy look: rasterise, warm paper tone, speckle, slight skew + blur, no text layer."""
    from PIL import Image, ImageFilter

    rng = random.Random(seed)
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as src:
        pix = src[0].get_pixmap(dpi=200)
    image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
    image = image.point(lambda p: int(p * 0.93 + 8))  # greyish paper, softer blacks
    px = image.load()
    for _ in range(2500):
        x, y = rng.randrange(image.width), rng.randrange(image.height)
        px[x, y] = rng.randrange(120, 200)
    image = image.rotate(rng.uniform(-0.9, 0.9), fillcolor=235, expand=False, resample=Image.BICUBIC)
    image = image.filter(ImageFilter.GaussianBlur(0.55))
    out = io.BytesIO()
    image.convert("RGB").save(out, format="JPEG", quality=68)
    doc = pymupdf.open()
    page = doc.new_page(width=W, height=H)
    page.insert_image(page.rect, stream=out.getvalue())
    data = doc.tobytes()
    doc.close()
    return data


def make_corrupted(source: bytes) -> bytes:
    """First third of a real invoice PDF, then garbage — a download that broke halfway."""
    rng = random.Random(13)
    return source[: len(source) // 3] + bytes(rng.randrange(256) for _ in range(900))


def write_spec(spec: Spec, folder: Path) -> None:
    target = folder / spec.file
    if spec.kind == "copy_of":
        shutil.copyfile(folder / spec.copy_of, target)
    elif spec.kind == "corrupted":
        target.write_bytes(make_corrupted((folder / "01_valid_invoice.pdf").read_bytes()))
    else:
        pdf = draw(spec)
        target.write_bytes(make_scanned(pdf) if spec.kind == "scanned" else pdf)


# ------------------------------------------------------------------ manifests
def _target(spec: Spec) -> Spec:
    return next(s for s in INVOICES if s.file == spec.copy_of) if spec.kind == "copy_of" else spec


def manifest_entry(spec: Spec) -> dict:
    t = _target(spec)
    total = str(t.amounts()[2]) if t.items else None
    return {
        "file": spec.file,
        "scenario": spec.scenario,
        "expected_outcome": spec.expected,
        "invoice_number": t.number,
        "vendor": t.vendor_name or None,
        "po_number": t.po,
        "currency": t.currency,
        "total": total,
        "layout": spec.kind if spec.kind in ("scanned", "corrupted") else t.layout,
        "description": spec.description,
        "edge_case_category": spec.category,
    }


def history_entry(spec: Spec, order: int) -> dict:
    subtotal, tax, total = spec.amounts()
    return {
        **manifest_entry(spec),
        "order": order,
        "vendor_code": spec.vendor_code,
        "gstin": spec.gstin,
        "vendor_address": spec.vendor_address,
        "bank_details": spec.bank_text(),
        "invoice_date": spec.date,
        "due_date": spec.due,
        "items": [
            {"description": d, "quantity": q, "unit_price": p, "tax_percentage": t, "total_amount": str(Decimal(str(p)) * q)}
            for d, q, p, t in spec.items
        ],
        "subtotal": str(subtotal),
        "tax": str(tax),
        "total": str(total),
        "resolve": list(spec.extra["resolve"]) if "resolve" in spec.extra else None,
    }


def write_frontend(manifest: list[dict]) -> None:
    public = FRONTEND / "public" / "samples"
    public.mkdir(parents=True, exist_ok=True)
    for old in public.glob("*.pdf"):
        old.unlink()
    for entry in manifest:
        shutil.copyfile(ROOT / "invoices" / entry["file"], public / entry["file"])
    body = json.dumps(manifest, indent=2, ensure_ascii=False)
    (FRONTEND / "lib" / "samples.ts").write_text(
        """export interface SampleInvoiceMeta {
  file: string;
  scenario: string;
  expected_outcome: "APPROVED" | "NEEDS_REVIEW" | "REJECTED" | "PROCESSING_FAILED";
  invoice_number: string | null;
  vendor: string | null;
  po_number: string | null;
  currency: string;
  total: string | null;
  layout: string;
  description: string;
  edge_case_category: string;
}

/** Test invoices (generated by scripts/generate_sample_invoices.py — do not edit by hand). */
export const SAMPLE_INVOICES: SampleInvoiceMeta[] = """
        + body
        + ";\n",
        encoding="utf-8",
    )


def main() -> None:
    for sub in ("invoices/history", "vendors", "purchase_orders"):
        (ROOT / sub).mkdir(parents=True, exist_ok=True)
    for old in list((ROOT / "invoices").glob("*.pdf")) + list((ROOT / "invoices" / "history").glob("*.pdf")):
        old.unlink()

    vendors = []
    for v in VENDOR_INFO:
        bank_name, account, ifsc = vendor_bank(v.code)
        vendors.append({
            "vendor_code": v.code, "vendor_name": v.name, "gstin": v.gstin, "address": v.one_line_address,
            "status": v.status, "email": v.email, "phone": v.phone, "bank_name": bank_name,
            "bank_account_number": account, "bank_ifsc": ifsc,
        })  # fmt: skip
    (ROOT / "vendors" / "vendors.json").write_text(json.dumps(vendors, indent=2), encoding="utf-8")

    pos = [
        {"po_number": n, "vendor_code": vc, "po_date": d, "currency": cur, "status": st, "description": desc,
         "items": [{"description": i, "quantity": q, "unit_price": p, "hsn_sac": item_meta(i)[0], "gst_rate": item_meta(i)[2]} for i, q, p in items],
         "total_amount": str(po_total(items))}
        for n, vc, d, cur, st, desc, items in POS
    ]  # fmt: skip
    (ROOT / "purchase_orders" / "purchase_orders.json").write_text(json.dumps(pos, indent=2), encoding="utf-8")

    history = []
    for order, spec in enumerate(HISTORY):
        write_spec(spec, ROOT / "invoices" / "history")
        history.append(history_entry(spec, order))
    (ROOT / "invoices" / "history" / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")

    for spec in sorted(INVOICES, key=lambda s: s.kind in ("copy_of", "corrupted")):
        write_spec(spec, ROOT / "invoices")
    manifest = [manifest_entry(s) for s in INVOICES]
    (ROOT / "invoices" / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_frontend(manifest)
    print(f"Generated {len(vendors)} vendors, {len(pos)} POs, {len(history)} history and {len(INVOICES)} test invoices")


if __name__ == "__main__":
    main()
