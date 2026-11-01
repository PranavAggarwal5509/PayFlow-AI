"""Document visual layout extractor.

Extracts word-level bounding boxes and page dimensions locally using:
1. PyMuPDF for digital text PDFs.
2. Tesseract OCR (image_to_data) for scanned/image PDFs.

Returns normalized coordinates [x0, y0, x1, y1] where 0.0 <= x, y <= 1.0
relative to the page width and height, or points with page dimensions.
"""

from dataclasses import dataclass, field
import io
import re
from typing import Literal
import pymupdf


@dataclass
class LayoutWord:
    text: str
    norm_text: str
    page: int  # 1-indexed
    # Absolute points on original page
    bbox: list[float]  # [x0, y0, x1, y1]
    # Normalized coordinates [0.0, 1.0]
    norm_bbox: list[float]  # [norm_x0, norm_y0, norm_x1, norm_y1]
    confidence: float = 100.0


@dataclass
class PageLayout:
    page_number: int  # 1-indexed
    width: float
    height: float
    words: list[LayoutWord] = field(default_factory=list)
    source: Literal["pdf_text", "tesseract"] = "pdf_text"


@dataclass
class DocumentLayout:
    pages: list[PageLayout] = field(default_factory=list)
    extraction_source: Literal["pdf_text", "tesseract"] = "pdf_text"


def normalize_val(s: str | None) -> str:
    """Normalize string for robust token matching."""
    if not s:
        return ""
    # Lowercase, remove commas, currency symbols, extra whitespace
    cleaned = re.sub(r"[\s,\.\-\/\:\₹\$\€\£]", "", str(s).lower())
    return cleaned


def extract_pdf_layout(pdf_bytes: bytes) -> DocumentLayout:
    """Extract word layout from a digital PDF using PyMuPDF."""
    doc_layout = DocumentLayout(pages=[], extraction_source="pdf_text")
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for pno, page in enumerate(doc, start=1):
            rect = page.rect
            w = float(rect.width) if rect.width > 0 else 1.0
            h = float(rect.height) if rect.height > 0 else 1.0
            page_layout = PageLayout(page_number=pno, width=w, height=h, words=[], source="pdf_text")

            # page.get_text("words") returns list of (x0, y0, x1, y1, word, block_no, line_no, word_no)
            words_data = page.get_text("words")
            for item in words_data:
                x0, y0, x1, y1, word_text = float(item[0]), float(item[1]), float(item[2]), float(item[3]), str(item[4])
                norm_w = normalize_val(word_text)
                if not norm_w:
                    continue
                norm_bbox = [
                    round(max(0.0, min(1.0, x0 / w)), 4),
                    round(max(0.0, min(1.0, y0 / h)), 4),
                    round(max(0.0, min(1.0, x1 / w)), 4),
                    round(max(0.0, min(1.0, y1 / h)), 4),
                ]
                page_layout.words.append(
                    LayoutWord(
                        text=word_text,
                        norm_text=norm_w,
                        page=pno,
                        bbox=[round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                        norm_bbox=norm_bbox,
                        confidence=100.0,
                    )
                )
            doc_layout.pages.append(page_layout)
    return doc_layout


def extract_ocr_layout(pdf_bytes: bytes, dpi: int = 150) -> DocumentLayout:
    """Extract word layout from a scanned PDF using PyMuPDF pixmaps and pytesseract image_to_data."""
    import pytesseract
    from PIL import Image

    doc_layout = DocumentLayout(pages=[], extraction_source="tesseract")
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for pno, page in enumerate(doc, start=1):
            rect = page.rect
            orig_w = float(rect.width) if rect.width > 0 else 1.0
            orig_h = float(rect.height) if rect.height > 0 else 1.0

            pix = page.get_pixmap(dpi=dpi)
            pix_w = float(pix.width) if pix.width > 0 else 1.0
            pix_h = float(pix.height) if pix.height > 0 else 1.0

            img = Image.open(io.BytesIO(pix.tobytes("png")))
            tsv_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

            page_layout = PageLayout(page_number=pno, width=orig_w, height=orig_h, words=[], source="tesseract")

            n_boxes = len(tsv_data["text"])
            for i in range(n_boxes):
                text_val = str(tsv_data["text"][i]).strip()
                if not text_val:
                    continue
                norm_w = normalize_val(text_val)
                if not norm_w:
                    continue

                conf = float(tsv_data["conf"][i]) if tsv_data["conf"][i] != "-1" else 50.0
                left = float(tsv_data["left"][i])
                top = float(tsv_data["top"][i])
                width = float(tsv_data["width"][i])
                height = float(tsv_data["height"][i])

                # Map pixmap pixels back to original page coordinates
                scale_x = orig_w / pix_w
                scale_y = orig_h / pix_h

                x0 = left * scale_x
                y0 = top * scale_y
                x1 = (left + width) * scale_x
                y1 = (top + height) * scale_y

                norm_bbox = [
                    round(max(0.0, min(1.0, x0 / orig_w)), 4),
                    round(max(0.0, min(1.0, y0 / orig_h)), 4),
                    round(max(0.0, min(1.0, x1 / orig_w)), 4),
                    round(max(0.0, min(1.0, y1 / orig_h)), 4),
                ]

                page_layout.words.append(
                    LayoutWord(
                        text=text_val,
                        norm_text=norm_w,
                        page=pno,
                        bbox=[round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                        norm_bbox=norm_bbox,
                        confidence=conf,
                    )
                )
            doc_layout.pages.append(page_layout)
    return doc_layout

