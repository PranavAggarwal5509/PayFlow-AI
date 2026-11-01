"""Locates visual evidence bounding boxes for extracted invoice fields.

Matches extracted field values (dates, amounts, numbers, vendor names, line items)
against the document layout (PyMuPDF word tokens or Tesseract OCR tokens).
"""

from typing import Any
from app.services.document_layout import DocumentLayout, LayoutWord, normalize_val


def merge_word_bboxes(words: list[LayoutWord], page_w: float, page_h: float) -> tuple[list[float], list[float]]:
    """Compute bounding box encompassing a contiguous sequence of words.

    Returns:
        (bbox_points [x0, y0, x1, y1], norm_bbox [nx0, ny0, nx1, ny1])
    """
    if not words:
        return [0, 0, 0, 0], [0, 0, 0, 0]
    x0 = min(w.bbox[0] for w in words)
    y0 = min(w.bbox[1] for w in words)
    x1 = max(w.bbox[2] for w in words)
    y1 = max(w.bbox[3] for w in words)

    norm_x0 = round(max(0.0, min(1.0, x0 / page_w)), 4)
    norm_y0 = round(max(0.0, min(1.0, y0 / page_h)), 4)
    norm_x1 = round(max(0.0, min(1.0, x1 / page_w)), 4)
    norm_y1 = round(max(0.0, min(1.0, y1 / page_h)), 4)

    return [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)], [norm_x0, norm_y0, norm_x1, norm_y1]


def find_value_in_layout(
    target_val: Any,
    layout: DocumentLayout,
    field_name: str | None = None,
) -> dict[str, Any] | None:
    """Find a target value (str, int, float, Decimal) in the document layout words.

    Returns an evidence dict:
    {
        "page": int,
        "bbox": [x0, y0, x1, y1],
        "norm_bbox": [nx0, ny0, nx1, ny1],
        "source": "pdf_text" | "tesseract",
        "evidence_status": "VERIFIED" | "AMBIGUOUS" | "NOT_FOUND",
        "text": str
    }
    """
    if target_val is None:
        return None

    str_val = str(target_val).strip()
    if not str_val:
        return None

    norm_target = normalize_val(str_val)
    if not norm_target:
        return None

    # Handle currency specifically: must match currency code/symbol tokens exactly,
    # never as a substring of an invoice number or identifier (e.g. 'USD' in 'KCT-USD-0112')
    is_currency_field = field_name == "currency"
    is_id_field = field_name in ("invoice_number", "purchase_order_number")

    # Handle decimal zero trimming for numbers (e.g. "14000.00" -> "14000")
    norm_variants = {norm_target}
    if "." in str_val:
        try:
            float_val = float(str_val)
            norm_variants.add(normalize_val(f"{float_val:.2f}"))
            norm_variants.add(normalize_val(f"{int(float_val)}"))
        except ValueError:
            pass

    # Split target into normalized sub-tokens for multi-word phrases
    target_tokens = [normalize_val(t) for t in str_val.split() if normalize_val(t)]

    matches_found: list[tuple[int, list[LayoutWord], float, float]] = []

    for page in layout.pages:
        words = page.words
        n_words = len(words)
        if n_words == 0:
            continue

        # Strategy 1: Exact single-word token match against target or variants
        for w in words:
            if is_currency_field:
                # Currency field must be an exact token match, or word text matches symbol
                # Ignore if word contains digits or hyphens (identifiers)
                if any(c.isdigit() for c in w.text):
                    continue
                if w.norm_text == norm_target or w.text.strip().upper() == str_val.upper():
                    matches_found.append((page.page_number, [w], page.width, page.height))
            elif is_id_field:
                # Identifiers must match exact token or target_tokens
                if w.norm_text in norm_variants or w.norm_text == norm_target:
                    matches_found.append((page.page_number, [w], page.width, page.height))
            else:
                if w.norm_text in norm_variants:
                    matches_found.append((page.page_number, [w], page.width, page.height))
                elif len(norm_target) >= 4 and norm_target in w.norm_text:
                    # Only allow substring match for long strings if not an ID or currency
                    matches_found.append((page.page_number, [w], page.width, page.height))

        # Strategy 2: Multi-word phrase sliding window
        if len(target_tokens) > 1 and not is_currency_field:
            k = len(target_tokens)
            for i in range(n_words - k + 1):
                window = words[i : i + k]
                if all(w.norm_text == t for w, t in zip(window, target_tokens)):
                    matches_found.append((page.page_number, window, page.width, page.height))

        # Strategy 3: Substring accumulation across contiguous words (e.g., date parts "21" "/" "10" "/" "2026")
        if not matches_found and not is_currency_field:
            for i in range(n_words):
                accum_text = ""
                window: list[LayoutWord] = []
                for j in range(i, min(i + 8, n_words)):
                    window.append(words[j])
                    accum_text += words[j].norm_text
                    if accum_text in norm_variants or (len(norm_target) >= 4 and norm_target in accum_text):
                        matches_found.append((page.page_number, window, page.width, page.height))
                        break
                    if len(accum_text) > len(norm_target) + 5:
                        break

    if not matches_found:
        return {
            "page": 1,
            "bbox": None,
            "norm_bbox": None,
            "source": layout.extraction_source,
            "evidence_status": "NOT_FOUND",
            "text": str_val,
        }

    # If exactly 1 match or picking the highest confidence one
    pno, matched_words, pw, ph = matches_found[0]
    bbox, norm_bbox = merge_word_bboxes(matched_words, pw, ph)
    status = "VERIFIED" if len(matches_found) == 1 else "AMBIGUOUS"

    return {
        "page": pno,
        "bbox": bbox,
        "norm_bbox": norm_bbox,
        "source": layout.extraction_source,
        "evidence_status": status,
        "text": " ".join(w.text for w in matched_words),
        "page_width": pw,
        "page_height": ph,
    }


def build_invoice_visual_evidence(
    extracted_data: dict[str, Any],
    layout: DocumentLayout,
) -> dict[str, Any]:
    """Generate visual evidence mapping for all structured invoice fields."""
    evidence: dict[str, Any] = {}

    # Header and financial fields
    header_fields = [
        "invoice_number",
        "invoice_date",
        "due_date",
        "vendor_name",
        "vendor_gstin",
        "purchase_order_number",
        "currency",
        "subtotal",
        "tax_amount",
        "total_amount",
    ]

    for field in header_fields:
        val = extracted_data.get(field)
        if val is not None:
            ev = find_value_in_layout(val, layout, field_name=field)
            if ev:
                evidence[field] = ev

    # Line items evidence
    line_items = extracted_data.get("line_items") or []
    lines_evidence: list[dict[str, Any]] = []

    for idx, item in enumerate(line_items):
        item_ev: dict[str, Any] = {"line_index": idx}
        for subfield in ("description", "quantity", "unit_price", "total_amount"):
            val = item.get(subfield)
            if val is not None:
                ev = find_value_in_layout(val, layout, field_name=subfield)
                if ev:
                    item_ev[subfield] = ev
        lines_evidence.append(item_ev)

    if lines_evidence:
        evidence["line_items"] = lines_evidence

    return evidence

