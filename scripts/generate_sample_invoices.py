"""Generate the synthetic dataset: JSON master data + invoice PDFs in three layouts.

Usage (from repo root):  python scripts/generate_sample_invoices.py
"""

import io
import json
import random
import shutil
import sys
from decimal import Decimal
from pathlib import Path

import pymupdf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).parent))
from sample_catalog import HISTORY, INVOICES, POS, VENDORS, Spec  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent / "sample_data"
W, H = A4
SYMBOL = {"INR": "Rs.", "USD": "USD"}


def fmt(amount: Decimal | float, currency: str) -> str:
    return f"{SYMBOL.get(currency, currency)} {Decimal(str(amount)):,.2f}"


def draw(spec: Spec) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4, invariant=True)
    c.setTitle(f"Invoice {spec.number or ''}".strip())
    {"classic": _classic, "modern": _modern, "compact": _compact}[spec.layout](c, spec)
    c.save()
    return buffer.getvalue()


def _party(c, spec, x, y, size=9):
    c.setFont("Helvetica-Bold", size + 3)
    c.drawString(x, y, spec.vendor_name)
    c.setFont("Helvetica", size)
    c.drawString(x, y - 14, spec.vendor_address)
    if spec.gstin:
        c.drawString(x, y - 27, f"GSTIN: {spec.gstin}")


def _meta(c, spec, x, y, gap=14):
    rows = [
        ("Invoice No", spec.number),
        ("Invoice Date", spec.date),
        ("Due Date", spec.due),
        ("PO Number", spec.po),
        ("Currency", spec.currency),
    ]
    for label, value in rows:
        if value is None:
            continue  # absent field is simply not printed
        c.setFont("Helvetica", 9)
        c.drawString(x, y, f"{label}:")
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 80, y, str(value))
        y -= gap


def _table(c, spec, top, left=40, right=None, header_fill=colors.HexColor("#e2e8f0")):
    right = right or W - 40
    c.setFillColor(header_fill)
    c.rect(left, top - 4, right - left, 18, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    cols = [left + 4, left + 250, left + 300, left + 370, left + 420]
    for x, label in zip(cols, ["Description", "Qty", "Unit Price", "Tax %", "Amount"]):
        c.drawString(x, top, label)
    y = top - 20
    c.setFont("Helvetica", 9)
    for desc, qty, price, tax in spec.items:
        c.drawString(cols[0], y, desc)
        c.drawString(cols[1], y, str(qty))
        c.drawString(cols[2], y, f"{Decimal(str(price)):,.2f}")
        c.drawString(cols[3], y, f"{tax}%")
        c.drawString(cols[4], y, f"{Decimal(str(price)) * qty:,.2f}")
        y -= 16
    return y - 6


def _totals(c, spec, y, x_label, x_value, bold_total=True):
    subtotal, tax, total = spec.amounts()
    for label, value in (("Subtotal", subtotal), ("Tax", tax)):
        c.setFont("Helvetica", 10)
        c.drawString(x_label, y, f"{label}:")
        c.drawRightString(x_value, y, fmt(value, spec.currency))
        y -= 15
    c.setFont("Helvetica-Bold" if bold_total else "Helvetica", 11)
    c.drawString(x_label, y, "Total Amount:")
    c.drawRightString(x_value, y, fmt(total, spec.currency))
    return y - 30


def _footer(c, spec, y, x=40):
    c.setFont("Helvetica", 8)
    c.drawString(x, y, "Payment terms: Net 30 days. Bank: DEMO BANK, A/C 0000123456789, IFSC DEMO0000123")
    c.drawString(x, y - 11, "This is a synthetic invoice generated for PayFlow AI demonstrations.")


def _classic(c, spec: Spec):
    _party(c, spec, 40, H - 60)
    c.setFont("Helvetica-Bold", 22)
    c.drawRightString(W - 40, H - 60, "TAX INVOICE")
    _meta(c, spec, 360, H - 90)
    c.line(40, H - 190, W - 40, H - 190)
    y = _table(c, spec, H - 215)
    y = _totals(c, spec, y - 10, 360, W - 40)
    _footer(c, spec, y)


def _modern(c, spec: Spec):
    c.setFillColor(colors.HexColor("#1e3a8a"))
    c.rect(0, H - 110, W, 110, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, H - 55, spec.vendor_name)
    c.setFont("Helvetica", 9)
    c.drawString(40, H - 72, spec.vendor_address)
    if spec.gstin:
        c.drawString(40, H - 85, f"GSTIN {spec.gstin}")
    c.setFont("Helvetica-Bold", 16)
    c.drawRightString(W - 40, H - 55, "INVOICE")
    c.setFillColor(colors.black)
    _meta(c, spec, 40, H - 140, gap=13)
    y = _table(c, spec, H - 235, header_fill=colors.HexColor("#dbeafe"))
    y = _totals(c, spec, y - 10, 340, W - 40)
    _footer(c, spec, y)


def _compact(c, spec: Spec):
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, H - 45, spec.vendor_name.upper())
    c.setFont("Helvetica", 8)
    c.drawString(40, H - 57, spec.vendor_address)
    if spec.gstin:
        c.drawString(40, H - 68, f"GST No.: {spec.gstin}")
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(W - 40, H - 45, "BILL / INVOICE")
    y = H - 100
    c.setFont("Helvetica", 8)
    parts = []
    if spec.number:
        parts.append(f"Bill #{spec.number}")
    parts.append(f"Dated {spec.date}")
    parts.append(f"Due {spec.due}")
    if spec.po:
        parts.append(f"Against PO {spec.po}")
    parts.append(f"All amounts in {spec.currency}")
    c.drawString(40, y, "  |  ".join(parts))
    y = _table(c, spec, y - 30, header_fill=colors.HexColor("#f1f5f9"))
    y = _totals(c, spec, y - 6, 380, W - 40, bold_total=False)
    _footer(c, spec, y)


def make_scanned(pdf_bytes: bytes, seed: int = 1) -> bytes:
    """Rasterise a digital PDF and re-wrap the pixels: no text layer, slight noise/skew."""
    rng = random.Random(seed)
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as src:
        pix = src[0].get_pixmap(dpi=170)
    from PIL import Image, ImageFilter

    image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
    image = image.rotate(rng.uniform(-0.6, 0.6), fillcolor=255, expand=False)
    image = image.filter(ImageFilter.GaussianBlur(0.6))
    out = io.BytesIO()
    image.convert("RGB").save(out, format="JPEG", quality=70)
    doc = pymupdf.open()
    page = doc.new_page(width=W, height=H)
    page.insert_image(page.rect, stream=out.getvalue())
    data = doc.tobytes()
    doc.close()
    return data


def make_corrupted() -> bytes:
    rng = random.Random(13)
    return b"%PDF-1.4\n%%corrupted demo file\n" + bytes(rng.randrange(256) for _ in range(600))


def write_spec(spec: Spec, folder: Path) -> None:
    target = folder / spec.file
    if spec.kind == "copy_of":
        shutil.copyfile(folder / spec.copy_of, target)
    elif spec.kind == "corrupted":
        target.write_bytes(make_corrupted())
    else:
        pdf = draw(spec)
        target.write_bytes(make_scanned(pdf) if spec.kind == "scanned" else pdf)


def manifest_entry(spec: Spec) -> dict:
    subtotal, tax, total = spec.amounts() if spec.items else (None, None, None)
    return {
        "file": spec.file,
        "scenario": spec.scenario,
        "expected_outcome": spec.expected,
        "invoice_number": spec.number,
        "vendor": spec.vendor_name or None,
        "po_number": spec.po,
        "currency": spec.currency,
        "total": str(total) if total is not None else None,
        "layout": spec.layout if spec.kind == "digital" else spec.kind,
    }


def main() -> None:
    for sub in ("invoices/history", "vendors", "purchase_orders"):
        (ROOT / sub).mkdir(parents=True, exist_ok=True)

    vendors = [
        {"vendor_code": c, "vendor_name": n, "gstin": g, "address": a, "status": s,
         "email": f"accounts@{c.lower().replace('-', '')}.example", "phone": f"+91-90000-{c[-4:]}"}
        for c, n, g, a, s in VENDORS
    ]  # fmt: skip
    (ROOT / "vendors" / "vendors.json").write_text(json.dumps(vendors, indent=2), encoding="utf-8")

    pos = [
        {"po_number": n, "vendor_code": v, "po_date": d, "currency": cur, "status": st,
         "description": desc, "items": [{"description": i, "quantity": q, "unit_price": p} for i, q, p in items],
         "total_amount": str(_po_total(items, cur))}
        for n, v, d, cur, st, desc, items in POS
    ]  # fmt: skip
    (ROOT / "purchase_orders" / "purchase_orders.json").write_text(json.dumps(pos, indent=2), encoding="utf-8")

    history = []
    for spec in HISTORY:
        write_spec(spec, ROOT / "invoices" / "history")
        history.append({**manifest_entry(spec), "days_ago": spec.extra["days_ago"],
                        "vendor_code": next(v[0] for v in VENDORS if v[1] == spec.vendor_name),
                        "gstin": spec.gstin, "invoice_date": spec.date, "due_date": spec.due,
                        "items": [{"description": d, "quantity": q, "unit_price": p, "tax_percentage": t}
                                  for d, q, p, t in spec.items],
                        "subtotal": str(spec.amounts()[0]), "tax": str(spec.amounts()[1])})  # fmt: skip
    (ROOT / "invoices" / "history" / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")

    for spec in INVOICES:
        write_spec(spec, ROOT / "invoices")
    manifest = [manifest_entry(s) for s in INVOICES]
    (ROOT / "invoices" / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Generated {len(VENDORS)} vendors, {len(POS)} POs, {len(HISTORY)} history and {len(INVOICES)} demo invoices")


def _po_total(items, currency) -> Decimal:
    # PO value includes 18% tax for INR so approved invoices (which carry tax) fit the PO.
    base = sum(Decimal(str(q)) * Decimal(str(p)) for _, q, p in items)
    return (base * Decimal("1.18") if currency == "INR" else base * Decimal("1.0")).quantize(Decimal("0.01"))


if __name__ == "__main__":
    main()

