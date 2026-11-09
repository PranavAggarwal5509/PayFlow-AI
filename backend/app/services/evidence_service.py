"""Visual evidence: where each extracted value sits on the original PDF page.

For every extracted field we look for the printed value in the document layout (PyMuPDF words for
digital PDFs, Tesseract words for scans) and return its bounding box, so a reviewer can click a
value and see it highlighted on the invoice.

Matching rules (deterministic, no AI):
* amounts / quantities are compared as numbers (1,14,460.00 == 114460 == ₹ 1,14,460), so 450.00
  is never confused with 45,000;
* dates are compared as dates in every common printed format (30-Oct-2026, 30/10/2026,
  30 Oct 2026, 2026-10-30);
* identifiers and names are compared as normalised token sequences;
* when a value is printed more than once, the occurrence next to the field's label wins
  ("Invoice No.", "Due Date", "Total" ...); line-item cells are anchored to their own row.

Each evidence entry:
    {"page", "bbox", "norm_bbox", "source", "evidence_status", "text", "page_width",
     "page_height", "match_count"}
evidence_status: VERIFIED (unique or clearly labelled), AMBIGUOUS (best guess among several),
NOT_FOUND (value not printed / unreadable).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.document_layout import DocumentLayout, LayoutWord, PageLayout, normalize_val
from app.utils.normalize import parse_bank_details

NUMERIC_FIELDS = {"subtotal", "tax_amount", "total_amount", "quantity", "unit_price", "line_total"}
DATE_FIELDS = {"invoice_date", "due_date"}

# Printed labels that sit next to a field's value (lower-case, matched as token sequences).
LABELS: dict[str, list[str]] = {
    "invoice_number": ["invoice no", "invoice #", "invoice number", "inv no", "bill #", "bill no"],
    "invoice_date": ["invoice date", "dated", "date", "bill date"],
    "due_date": ["due date", "payment due date", "due"],
    "purchase_order_number": ["buyer's order no", "po number", "client po no", "po no", "purchase order", "order no"],
    "vendor_gstin": ["gstin/uin", "gstin", "supplier gstin", "gst no"],
    "subtotal": ["taxable value", "taxable amount", "sub total", "subtotal", "taxable"],
    "tax_amount": ["total gst", "total tax", "tax amount", "total tax amount"],
    "total_amount": ["invoice total", "grand total", "total", "amount payable", "net payable"],
    "currency": ["currency", "amounts in"],
    "bank_account_number": ["a/c no", "account no", "a/c", "account number"],
    "bank_ifsc": ["ifsc", "ifs code", "ifsc code"],
}

_DATE_FORMATS = ("%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%b %d %Y", "%d-%b-%y", "%d/%m/%y")


# ------------------------------------------------------------------ value parsing
def _number(text: str) -> Decimal | None:
    cleaned = re.sub(r"(?i)^(rs\.?|inr|₹|\$|usd)", "", text.strip()).replace(",", "").replace("₹", "")
    cleaned = cleaned.rstrip("/-").strip()
    if not re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _date(text: str) -> date | None:
    t = text.strip().rstrip(",.").replace("  ", " ")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


_OCR_FOLD = str.maketrans({"o": "0", "d": "0", "q": "0", "i": "1", "l": "1", "|": "1", "s": "5", "b": "8", "z": "2", "g": "6"})


def _fold(text: str) -> str:
    return text.lower().translate(_OCR_FOLD)


# ------------------------------------------------------------------ geometry helpers
def merge_word_bboxes(words: list[LayoutWord], page_w: float, page_h: float) -> tuple[list[float], list[float]]:
    """Bounding box around a run of words: (points [x0, y0, x1, y1], normalised [0..1])."""
    if not words:
        return [0, 0, 0, 0], [0, 0, 0, 0]
    x0 = min(w.bbox[0] for w in words)
    y0 = min(w.bbox[1] for w in words)
    x1 = max(w.bbox[2] for w in words)
    y1 = max(w.bbox[3] for w in words)
    norm = [
        round(max(0.0, min(1.0, x0 / page_w)), 4),
        round(max(0.0, min(1.0, y0 / page_h)), 4),
        round(max(0.0, min(1.0, x1 / page_w)), 4),
        round(max(0.0, min(1.0, y1 / page_h)), 4),
    ]
    return [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)], norm


@dataclass
class _Match:
    page: PageLayout
    words: list[LayoutWord]

    @property
    def x0(self) -> float:
        return min(w.bbox[0] for w in self.words)

    @property
    def x1(self) -> float:
        return max(w.bbox[2] for w in self.words)

    @property
    def y0(self) -> float:
        return min(w.bbox[1] for w in self.words)

    @property
    def y1(self) -> float:
        return max(w.bbox[3] for w in self.words)

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return self.y1 - self.y0


def _to_evidence(match: _Match, layout: DocumentLayout, status: str, count: int) -> dict[str, Any]:
    bbox, norm = merge_word_bboxes(match.words, match.page.width, match.page.height)
    return {
        "page": match.page.page_number,
        "bbox": bbox,
        "norm_bbox": norm,
        "source": layout.extraction_source,
        "evidence_status": status,
        "text": " ".join(w.text for w in match.words),
        "page_width": match.page.width,
        "page_height": match.page.height,
        "match_count": count,
    }


def _not_found(value: Any, layout: DocumentLayout) -> dict[str, Any]:
    return {
        "page": 1, "bbox": None, "norm_bbox": None, "source": layout.extraction_source,
        "evidence_status": "NOT_FOUND", "text": str(value), "match_count": 0,
    }  # fmt: skip


# ------------------------------------------------------------------ candidate search
def _candidates(value: Any, layout: DocumentLayout, field_name: str | None) -> list[_Match]:
    text = str(value).strip()
    out: list[_Match] = []
    numeric = field_name in NUMERIC_FIELDS or (field_name is None and _number(text) is not None and not _date(text))
    target_num = _number(text) if numeric else None
    target_date = _date(text) if (field_name in DATE_FIELDS or (field_name is None and _date(text))) else None
    tokens = [normalize_val(t) for t in text.split() if normalize_val(t)]
    joined = "".join(tokens)

    for page in layout.pages:
        words = page.words
        n = len(words)
        for i, w in enumerate(words):
            if target_num is not None:
                v = _number(w.text)
                if v is not None and v == target_num:
                    out.append(_Match(page, [w]))
                continue
            if target_date is not None:
                for k in (1, 2, 3):  # "30-Oct-2026" | "30 Oct 2026"
                    if i + k <= n and _date(" ".join(x.text for x in words[i : i + k])) == target_date:
                        out.append(_Match(page, words[i : i + k]))
                        break
                continue
            if not joined:
                continue
            if field_name == "currency":
                if w.text.strip().upper() == text.upper():
                    out.append(_Match(page, [w]))
                continue
            # Token-sequence match, tolerant of how the PDF split the words.
            acc, run = "", []
            for j in range(i, min(i + max(len(tokens) + 4, 6), n)):
                piece = words[j].norm_text
                if not joined.startswith(acc + piece):
                    break
                acc += piece
                run.append(words[j])
                if acc == joined:
                    out.append(_Match(page, list(run)))
                    break
    # Fall back to a substring hit for long identifiers glued to neighbours ("No.:ACM/2026/1042").
    if not out and not numeric and target_date is None and len(joined) >= 6 and field_name != "currency":
        for page in layout.pages:
            for w in page.words:
                if joined in w.norm_text:
                    out.append(_Match(page, [w]))
    # Scans: OCR swaps look-alike characters (O/0, I/1, S/5, B/8) and drops separators, so long
    # identifiers (account numbers, IFSC, GSTIN) are compared after folding, with a small tolerance.
    if not out and not numeric and target_date is None and layout.extraction_source == "tesseract" and len(joined) >= 8:
        from rapidfuzz import fuzz

        target = _fold(joined)
        for page in layout.pages:
            for w in page.words:
                if len(w.norm_text) >= 6 and fuzz.ratio(target, _fold(w.norm_text)) >= 88:
                    out.append(_Match(page, [w]))
    # Keep only the innermost of overlapping duplicates.
    unique: list[_Match] = []
    for m in out:
        if not any(m.page is u.page and m.words == u.words for u in unique):
            unique.append(m)
    return unique


def _label_distance(match: _Match, labels: list[str]) -> float:
    """Distance (points) from the match to the nearest printed label for its field."""
    words = match.page.words
    best = 10_000.0
    for label in labels:
        parts = [normalize_val(p) for p in label.split() if normalize_val(p)]
        if not parts:
            continue
        k = len(parts)
        for i in range(len(words) - k + 1):
            if any(words[i + t].norm_text != parts[t] for t in range(k)):
                continue
            lx1 = words[i + k - 1].bbox[2]
            lx0 = words[i].bbox[0]
            ly = (words[i].bbox[1] + words[i].bbox[3]) / 2
            dy = match.cy - ly
            if abs(dy) <= max(match.height, 6) * 0.8 and lx1 <= match.x0 + 2:  # same line, label on the left
                d = match.x0 - lx1
            elif 0 < dy <= 40 and lx0 - 30 <= match.x0 <= lx1 + 160:  # label just above
                d = dy * 1.5 + abs(match.x0 - lx0) * 0.2
            else:
                continue
            best = min(best, d)
    return best


def _pick(cands: list[_Match], field_name: str | None, anchor: _Match | None = None, prefer: str | None = None) -> tuple[_Match, str]:
    if len(cands) == 1:
        return cands[0], "VERIFIED"
    if anchor is not None:  # line-item cell: must sit on the anchor's row
        same_page = [c for c in cands if c.page is anchor.page]
        if same_page:
            def row_dist(c: _Match) -> float:
                return abs(c.cy - anchor.cy)
            near = sorted(same_page, key=row_dist)
            row = [c for c in near if row_dist(c) <= max(anchor.height, 6)]
            if row:
                if len(row) > 1 and prefer == "left":
                    row.sort(key=lambda c: c.x0)
                elif len(row) > 1 and prefer == "right":
                    row.sort(key=lambda c: -c.x1)
                return row[0], "VERIFIED"
            return near[0], "AMBIGUOUS"
    if field_name == "vendor_name":  # letterhead: the largest, then the top-most occurrence
        best = sorted(cands, key=lambda c: (-round(c.height), c.page.page_number, c.y0))[0]
        return best, "VERIFIED"
    labels = LABELS.get(field_name or "")
    if labels:
        scored = sorted(cands, key=lambda c: (_label_distance(c, labels), c.page.page_number, c.y0))
        d0 = _label_distance(scored[0], labels)
        d1 = _label_distance(scored[1], labels)
        if d0 < 250 and d1 - d0 > 15:
            return scored[0], "VERIFIED"
        return scored[0], "AMBIGUOUS"
    return cands[0], "AMBIGUOUS"


def find_value_in_layout(
    target_val: Any,
    layout: DocumentLayout,
    field_name: str | None = None,
    *,
    anchor: _Match | None = None,
    prefer: str | None = None,
) -> dict[str, Any] | None:
    """Locate one printed value; returns an evidence dict (see module docstring) or None if empty."""
    match, ev = _locate(target_val, layout, field_name, anchor=anchor, prefer=prefer)
    return ev


def _locate(target_val: Any, layout: DocumentLayout, field_name: str | None, *, anchor=None, prefer=None):
    if target_val is None or not str(target_val).strip() or not normalize_val(str(target_val)):
        return None, None
    cands = _candidates(target_val, layout, field_name)
    if not cands:
        return None, _not_found(target_val, layout)
    match, status = _pick(cands, field_name, anchor, prefer)
    return match, _to_evidence(match, layout, status, len(cands))


def _union(matches: list[_Match], layout: DocumentLayout, status: str) -> dict[str, Any] | None:
    matches = [m for m in matches if m is not None]
    if not matches:
        return None
    page = matches[0].page
    words = [w for m in matches if m.page is page for w in m.words]
    return _to_evidence(_Match(page, words), layout, status, 1)


# ------------------------------------------------------------------ public entry point
def build_invoice_visual_evidence(extracted_data: dict[str, Any], layout: DocumentLayout) -> dict[str, Any]:
    """Evidence for every extracted field, line-item cell and the remittance details."""
    evidence: dict[str, Any] = {}

    for field in ("invoice_number", "invoice_date", "due_date", "vendor_name", "vendor_gstin",
                  "purchase_order_number", "currency", "subtotal", "tax_amount", "total_amount"):  # fmt: skip
        _, ev = _locate(extracted_data.get(field), layout, field)
        if ev:
            evidence[field] = ev

    # Intra-state invoices often print only CGST and SGST (each half the tax), never the total GST.
    tax = extracted_data.get("tax_amount")
    if tax not in (None, "") and evidence.get("tax_amount", {}).get("evidence_status") in (None, "NOT_FOUND"):
        half = _number(str(tax))
        if half is not None:
            halves = _candidates(str(half / 2), layout, "tax_amount")
            labelled = sorted(halves, key=lambda c: _label_distance(c, ["cgst", "sgst", "utgst"]))
            pair = [c for c in labelled if _label_distance(c, ["cgst", "sgst", "utgst"]) < 250][:2]
            if len(pair) == 2 and pair[0].page is pair[1].page:
                union = _union(pair, layout, "VERIFIED")
                union["text"] = f"CGST {pair[0].words[0].text} + SGST {pair[1].words[0].text}"
                evidence["tax_amount"] = union

    # Remittance details: account number and IFSC, plus one box around both when on the same line.
    account, ifsc = parse_bank_details(extracted_data.get("bank_account_details"))
    acc_match, acc_ev = _locate(account, layout, "bank_account_number") if account else (None, None)
    ifsc_match, ifsc_ev = _locate(ifsc, layout, "bank_ifsc") if ifsc else (None, None)
    if acc_ev:
        evidence["bank_account_number"] = acc_ev
    if ifsc_ev:
        evidence["bank_ifsc"] = ifsc_ev
    if acc_match and ifsc_match and acc_match.page is ifsc_match.page and abs(acc_match.cy - ifsc_match.cy) < 40:
        evidence["bank_account_details"] = _union([acc_match, ifsc_match], layout, acc_ev["evidence_status"])
    elif acc_ev or ifsc_ev:
        evidence["bank_account_details"] = acc_ev or ifsc_ev

    lines: list[dict[str, Any]] = []
    for idx, item in enumerate(extracted_data.get("line_items") or []):
        row: dict[str, Any] = {"line_index": idx}
        desc_match, desc_ev = _locate(item.get("description"), layout, "description")
        if desc_ev:
            row["description"] = desc_ev
        cells: list[_Match] = [desc_match] if desc_match else []
        for sub, field, prefer in (("quantity", "quantity", None), ("unit_price", "unit_price", "left"),
                                   ("total_amount", "line_total", "right")):  # fmt: skip
            m, ev = _locate(item.get(sub), layout, field, anchor=desc_match, prefer=prefer)
            if ev:
                row[sub] = ev
            if m and desc_match and m.page is desc_match.page and abs(m.cy - desc_match.cy) <= max(desc_match.height, 6):
                cells.append(m)
        if cells:
            row["row"] = _union(cells, layout, desc_ev["evidence_status"] if desc_ev else "AMBIGUOUS")
        lines.append(row)
    if lines:
        evidence["line_items"] = lines
    return evidence


def rebuild_evidence(invoice, storage) -> bool:
    """Recompute evidence for a stored invoice (used by the pipeline and the backfill script)."""
    from app.services.document_layout import extract_ocr_layout, extract_pdf_layout

    if not invoice.extracted_data or not invoice.stored_file_path:
        return False
    pdf_bytes = storage.read(invoice.stored_file_path)
    layout = extract_ocr_layout(pdf_bytes) if invoice.extraction_method == "OCR" else extract_pdf_layout(pdf_bytes)
    invoice.visual_evidence = build_invoice_visual_evidence(invoice.extracted_data, layout)
    return True
