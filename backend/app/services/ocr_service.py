"""OCR fallback for scanned PDFs: render pages with PyMuPDF, read them with Tesseract."""

import io
import logging

import pymupdf

from app.core.errors import ProcessingError
from app.services.pdf_extractor import ExtractedDocument

logger = logging.getLogger(__name__)


def ocr_document(pdf_bytes: bytes, dpi: int = 200) -> ExtractedDocument:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise ProcessingError("OCR is not available on this server.", category="OCR_FAILED") from exc

    pages: list[str] = []
    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                pixmap = page.get_pixmap(dpi=dpi)
                image = Image.open(io.BytesIO(pixmap.tobytes("png")))
                pages.append(pytesseract.image_to_string(image))
    except pytesseract.TesseractNotFoundError as exc:
        logger.error("Tesseract binary not found", extra={"error_category": "OCR_FAILED"})
        raise ProcessingError(
            "OCR engine is not installed on the server.", category="OCR_FAILED"
        ) from exc
    except Exception as exc:
        logger.exception("OCR failed", extra={"error_category": "OCR_FAILED"})
        raise ProcessingError(
            "Text could not be read from the scanned document.", category="OCR_FAILED"
        ) from exc

    document = ExtractedDocument(pages=pages, method="OCR")
    if document.chars_per_page() < 10:
        raise ProcessingError(
            "The scanned document did not contain readable text.", category="OCR_FAILED"
        )
    return document

