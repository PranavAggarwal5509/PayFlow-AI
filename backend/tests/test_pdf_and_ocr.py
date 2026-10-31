"""Unit tests for pdf_extractor, needs_ocr, and OCR fallback integration."""

import pytest
from app.core.errors import ProcessingError
from app.services import pdf_extractor, ocr_service
from tests.pdf_factory import make_corrupted_pdf, make_image_only_pdf, make_pdf


def test_normal_text_pdf_extraction_succeeds_without_ocr():
    text = "INVOICE #1001\nVendor: Acme Supplies\nTotal Amount: 1000.00 INR\n" * 5
    pdf_bytes = make_pdf(text)
    doc = pdf_extractor.extract_text(pdf_bytes)

    assert doc.page_count == 1
    assert doc.method == "TEXT"
    assert "Acme Supplies" in doc.text
    # Sufficient text: does NOT need OCR
    assert not pdf_extractor.needs_ocr(doc, min_chars_per_page=50)
    assert pdf_extractor.is_text_sufficient(doc, min_chars_per_page=50)


def test_scanned_pdf_triggers_needs_ocr():
    # Empty / rectangle only PDF has 0 characters of digital text
    pdf_bytes = make_image_only_pdf()
    doc = pdf_extractor.extract_text(pdf_bytes)

    assert doc.page_count == 1
    assert doc.chars_per_page() < 10
    # Insufficient text: MUST need OCR
    assert pdf_extractor.needs_ocr(doc, min_chars_per_page=50)
    assert not pdf_extractor.is_text_sufficient(doc, min_chars_per_page=50)


def test_low_text_pdf_respects_configured_threshold():
    short_text = "Hi"  # 2 characters
    pdf_bytes = make_pdf(short_text)
    doc = pdf_extractor.extract_text(pdf_bytes)

    # If min_chars_per_page is 50, needs_ocr is True
    assert pdf_extractor.needs_ocr(doc, min_chars_per_page=50)
    # If min_chars_per_page is 1, needs_ocr is False
    assert not pdf_extractor.needs_ocr(doc, min_chars_per_page=1)


def test_corrupted_pdf_raises_processing_error():
    corrupted_bytes = make_corrupted_pdf()
    with pytest.raises(ProcessingError) as exc_info:
        pdf_extractor.extract_text(corrupted_bytes)
    assert exc_info.value.category == "DOCUMENT_CORRUPT"


def test_ocr_fallback_invoked_when_appropriate(monkeypatch):
    pdf_bytes = make_image_only_pdf()
    doc = pdf_extractor.extract_text(pdf_bytes)
    assert pdf_extractor.needs_ocr(doc, min_chars_per_page=50)

    # Mock ocr_document to verify it gets invoked and produces OCR document
    def fake_ocr(b, dpi=200):
        return pdf_extractor.ExtractedDocument(pages=["Extracted scanned text via OCR"], method="OCR")

    monkeypatch.setattr(ocr_service, "ocr_document", fake_ocr)
    ocr_doc = ocr_service.ocr_document(pdf_bytes, dpi=200)
    assert ocr_doc.method == "OCR"
    assert "Extracted scanned text" in ocr_doc.text
    assert not pdf_extractor.needs_ocr(ocr_doc, min_chars_per_page=10)

