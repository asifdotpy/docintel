"""OCR for images and scanned PDFs using Tesseract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image

    _OCR_AVAILABLE = True
except Exception:  # noqa: BLE001
    _OCR_AVAILABLE = False


def _cleanup(image: Any) -> Any:
    gray = image.convert("L")
    # Simple threshold to improve OCR on light backgrounds.
    return gray.point(lambda p: 0 if p < 128 else 255, mode="1")


def image(path: str | Path) -> str:
    """OCR a single image file. Returns extracted text (empty on failure)."""
    if not _OCR_AVAILABLE:
        raise RuntimeError("OCR dependencies are not installed (tesseract/pytesseract).")
    try:
        with Image.open(path) as img:
            cleaned = _cleanup(img)
            text = pytesseract.image_to_string(cleaned)
        return (text or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def pdf(path: str | Path) -> dict[str, Any]:
    """OCR a (scanned) PDF. Returns {text, page_count, error}."""
    if not _OCR_AVAILABLE:
        raise RuntimeError("OCR dependencies are not installed (tesseract/pytesseract).")
    try:
        pages = convert_from_path(str(path))
    except Exception:  # noqa: BLE001
        return {"text": "", "page_count": 0, "error": True}
    texts: list[str] = []
    for page in pages:
        try:
            cleaned = _cleanup(page)
            texts.append(pytesseract.image_to_string(cleaned) or "")
        except Exception:  # noqa: BLE001
            texts.append("")
    text = "\n".join(texts).strip()
    return {"text": text, "page_count": len(pages), "error": False}
