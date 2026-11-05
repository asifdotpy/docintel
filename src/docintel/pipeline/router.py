"""Route a file to the appropriate parser."""

from __future__ import annotations

import os
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
SPREADSHEET_EXTENSIONS = {".xlsx", ".xls", ".csv"}
PDF_EXTENSIONS = {".pdf"}


def _extension(path: str | os.PathLike) -> str:
    return Path(path).suffix.lower()


def detect(path: str | os.PathLike) -> str:
    """Return one of: pdf_text, pdf_ocr, image, spreadsheet.

    Raises ValueError for unsupported formats.
    """
    ext = _extension(path)
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in SPREADSHEET_EXTENSIONS:
        return "spreadsheet"
    if ext in PDF_EXTENSIONS:
        # Try to read the text layer; fall back to OCR if empty.
        try:
            from .pdf_text import extract

            result = extract(path)
        except Exception:  # noqa: BLE001
            return "pdf_ocr"
        text = (result.get("text") or "").strip()
        if text:
            return "pdf_text"
        return "pdf_ocr"
    raise ValueError(f"Unsupported file format: {ext or '<none>'}")
