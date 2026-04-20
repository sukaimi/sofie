"""PDF brand guidelines extractor.

When a brief links to a PDF (brand guidelines), this module reads each
page, sends them to Claude vision, and extracts brand elements:
colours, typography, logo description, tone, and any layout rules.
"""

import io
from pathlib import Path
from typing import Any

import fitz  # pymupdf


def pdf_to_page_images(pdf_path: str | Path, max_pages: int = 10, dpi: int = 150) -> list[bytes]:
    """Convert PDF pages to PNG images for vision analysis.

    Caps at max_pages to control token cost. 150 DPI is enough for
    Claude vision to read text and identify visual elements.
    """
    doc = fitz.open(str(pdf_path))
    images = []

    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        images.append(pix.tobytes("png"))

    doc.close()
    return images


def extract_text_from_pdf(pdf_path: str | Path, max_pages: int = 10) -> str:
    """Extract raw text from PDF pages for keyword analysis."""
    doc = fitz.open(str(pdf_path))
    texts = []

    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        texts.append(page.get_text())

    doc.close()
    return "\n---\n".join(texts)


def extract_images_from_pdf(
    pdf_path: str | Path, min_size: int = 200, max_images: int = 5
) -> list[dict[str, Any]]:
    """Extract embedded images from a PDF.

    Returns images larger than min_size pixels on any side.
    Each result has: bytes, width, height, page number.
    Used to find logos and hero images inside brand guidelines PDFs.
    """
    doc = fitz.open(str(pdf_path))
    images = []

    for page_num, page in enumerate(doc):
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                # Convert CMYK to RGB
                if pix.n > 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                elif pix.n == 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                if pix.width >= min_size or pix.height >= min_size:
                    images.append({
                        "bytes": pix.tobytes("png"),
                        "width": pix.width,
                        "height": pix.height,
                        "page": page_num,
                    })

                if len(images) >= max_images:
                    break
            except Exception:
                continue

        if len(images) >= max_images:
            break

    doc.close()
    return images


BRAND_EXTRACTION_PROMPT = (
    "You are analysing a brand guidelines PDF. Extract the following "
    "information from the pages shown. If a field is not visible, say 'not found'.\n\n"
    "Return ONLY valid JSON:\n"
    "{\n"
    '  "brand_colours": ["#hex1", "#hex2", ...],\n'
    '  "primary_colour": "#hex",\n'
    '  "secondary_colour": "#hex",\n'
    '  "font_names": ["Font Name 1", "Font Name 2"],\n'
    '  "primary_font": "Font Name",\n'
    '  "logo_description": "Describe the logo: shape, colours, style, any text in it",\n'
    '  "brand_tone": "e.g. professional, playful, minimal, bold",\n'
    '  "layout_rules": ["any specific layout rules mentioned"],\n'
    '  "do_nots": ["any restrictions or things to avoid"]\n'
    "}\n\n"
    "Be specific about colours — use hex codes where visible. "
    "For fonts, name the exact typeface if shown."
)
