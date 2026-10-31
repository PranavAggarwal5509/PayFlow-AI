"""Digital-PDF text extraction with PyMuPDF."""

from dataclasses import dataclass, field

import pymupdf

from app.core.errors import ProcessingError


@dataclass
class ExtractedDocument:
    pages: list[str] = field(default_factory=list)
    method: str = "TEXT"

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def text(self) -> str:
        return "\n\n".join(f"--- Page {i} ---\n{t}" for i, t in enumerate(self.pages, start=1))

    def chars_per_page(self) -> float:
        if not self.pages:
            return 0.0
        return sum(len(p.strip()) for p in self.pages) / len(self.pages)


def extract_text(pdf_bytes: bytes) -> ExtractedDocument:
    """Raise ProcessingError(DOCUMENT_CORRUPT) for unreadable files."""
    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
            if doc.needs_pass:
                raise ProcessingError(
                    "The PDF is password protected and cannot be read.", category="DOCUMENT_CORRUPT"
                )
            if doc.page_count == 0:
                raise ProcessingError("The PDF has no pages.", category="DOCUMENT_CORRUPT")
            return ExtractedDocument(pages=[page.get_text("text") for page in doc], method="TEXT")
    except ProcessingError:
        raise
    except Exception as exc:  # PyMuPDF raises several unrelated types for broken files
        raise ProcessingError(
            "The PDF file is corrupted or unreadable.", category="DOCUMENT_CORRUPT"
        ) from exc


def is_text_sufficient(document: ExtractedDocument, min_chars_per_page: int) -> bool:
    return document.chars_per_page() >= min_chars_per_page


def needs_ocr(document: ExtractedDocument, min_chars_per_page: int) -> bool:
    """Return True if the digital text extracted is below the threshold and requires OCR."""
    return not is_text_sufficient(document, min_chars_per_page)


