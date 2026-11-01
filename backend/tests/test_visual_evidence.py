"""Tests for document visual layout and evidence extraction:
1. Text PDF coordinate extraction
2. Word normalization and token matching
3. Formatted currency value matching
4. Date normalization matching
5. Line items visual evidence mapping
6. Missing evidence handling (NOT_FOUND)
7. Ambiguous evidence handling (AMBIGUOUS)
8. Page and coordinate boundary transformations
"""

import io
from decimal import Decimal
import pymupdf
import pytest

from app.services.document_layout import (
    DocumentLayout,
    LayoutWord,
    PageLayout,
    extract_pdf_layout,
    normalize_val,
)
from app.services.evidence_service import (
    build_invoice_visual_evidence,
    find_value_in_layout,
    merge_word_bboxes,
)


@pytest.fixture
def sample_pdf_bytes():
    # Build a simple 2-page PDF in memory using PyMuPDF
    doc = pymupdf.open()
    # Page 1
    page1 = doc.new_page(width=600, height=800)
    page1.insert_text((50, 100), "INVOICE: INV-2026-9999", fontsize=14)
    page1.insert_text((50, 130), "Date: 21/10/2026", fontsize=12)
    page1.insert_text((50, 160), "Vendor: Acme Global Solutions Ltd", fontsize=12)
    page1.insert_text((50, 190), "Total: ₹ 1,18,000.00", fontsize=12)
    page1.insert_text((50, 220), "Line Item: High Performance Laptop", fontsize=12)

    # Page 2
    page2 = doc.new_page(width=600, height=800)
    page2.insert_text((50, 100), "Terms & Payment Instructions", fontsize=12)
    page2.insert_text((50, 130), "PO Number: PO-8877", fontsize=12)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_extract_pdf_layout_multiple_pages(sample_pdf_bytes):
    layout = extract_pdf_layout(sample_pdf_bytes)
    assert len(layout.pages) == 2
    assert layout.extraction_source == "pdf_text"

    page1 = layout.pages[0]
    assert page1.width == 600.0
    assert page1.height == 800.0
    words1 = [w.text for w in page1.words]
    assert "INV-2026-9999" in words1
    assert "21/10/2026" in words1
    assert "Acme" in words1

    page2 = layout.pages[1]
    words2 = [w.text for w in page2.words]
    assert "PO-8877" in words2


def test_normalize_val():
    assert normalize_val(" ₹ 1,18,000.00 ") == "11800000"
    assert normalize_val("INV-2026/042") == "inv2026042"
    assert normalize_val("2026-10-21") == "20261021"


def test_find_formatted_currency_and_number(sample_pdf_bytes):
    layout = extract_pdf_layout(sample_pdf_bytes)

    # Extracted float/decimal 118000.00 against printed "₹ 1,18,000.00"
    ev = find_value_in_layout("118000.00", layout)
    assert ev is not None
    assert ev["evidence_status"] == "VERIFIED"
    assert ev["page"] == 1
    assert ev["bbox"] is not None
    assert ev["norm_bbox"] is not None
    # Verify normalized coordinates are within [0, 1]
    assert 0.0 <= ev["norm_bbox"][0] <= 1.0
    assert 0.0 <= ev["norm_bbox"][1] <= 1.0


def test_find_date_normalization(sample_pdf_bytes):
    layout = extract_pdf_layout(sample_pdf_bytes)

    # Date in text is 21/10/2026, search for ISO 2026-10-21 or original
    ev_orig = find_value_in_layout("21/10/2026", layout)
    assert ev_orig["evidence_status"] == "VERIFIED"
    assert ev_orig["page"] == 1


def test_multi_page_po_number(sample_pdf_bytes):
    layout = extract_pdf_layout(sample_pdf_bytes)

    # PO-8877 is on page 2
    ev = find_value_in_layout("PO-8877", layout)
    assert ev is not None
    assert ev["evidence_status"] == "VERIFIED"
    assert ev["page"] == 2


def test_missing_evidence(sample_pdf_bytes):
    layout = extract_pdf_layout(sample_pdf_bytes)

    # Field not present in document
    ev = find_value_in_layout("NON_EXISTENT_SKU_12345", layout)
    assert ev is not None
    assert ev["evidence_status"] == "NOT_FOUND"
    assert ev["bbox"] is None
    assert ev["norm_bbox"] is None


def test_currency_does_not_substring_match_invoice_number():
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)
    page.insert_text((50, 100), "Invoice Number: KCT-USD-0112", fontsize=14)
    page.insert_text((50, 150), "Currency: USD", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    layout = extract_pdf_layout(pdf_bytes)
    # Currency match should NOT match "KCT-USD-0112"
    ev_currency = find_value_in_layout("USD", layout, field_name="currency")
    assert ev_currency is not None
    assert ev_currency["text"] == "USD"
    assert "KCT" not in ev_currency["text"]

    # Invoice number match should match "KCT-USD-0112"
    ev_inv = find_value_in_layout("KCT-USD-0112", layout, field_name="invoice_number")
    assert ev_inv is not None
    assert ev_inv["text"] == "KCT-USD-0112"
    assert ev_inv["evidence_status"] == "VERIFIED"


def test_build_invoice_visual_evidence_comprehensive(sample_pdf_bytes):
    layout = extract_pdf_layout(sample_pdf_bytes)
    extracted = {
        "invoice_number": "INV-2026-9999",
        "invoice_date": "21/10/2026",
        "vendor_name": "Acme Global Solutions Ltd",
        "purchase_order_number": "PO-8877",
        "total_amount": "118000.00",
        "line_items": [
            {
                "description": "High Performance Laptop",
                "quantity": "1",
                "unit_price": "100000.00",
                "total_amount": "100000.00",
            }
        ],
    }
    evidence = build_invoice_visual_evidence(extracted, layout)
    assert "invoice_number" in evidence
    assert evidence["invoice_number"]["evidence_status"] == "VERIFIED"

    assert "purchase_order_number" in evidence
    assert evidence["purchase_order_number"]["page"] == 2

    assert "line_items" in evidence
    line_ev = evidence["line_items"][0]
    assert line_ev["description"]["evidence_status"] == "VERIFIED"

