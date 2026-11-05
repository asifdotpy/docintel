"""Extract text from digital PDFs using pypdf."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader


class PdfTextError(Exception):
    """Raised when a PDF cannot be read at all."""


def extract(path: str | Path) -> dict[str, Any]:
    """Extract text and page count from a digital PDF.

    Returns {"text": str, "page_count": int}.
    Raises PdfTextError for unreadable/corrupt/encrypted files.
    """
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise PdfTextError(f"Cannot read PDF: {exc}") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise PdfTextError(f"Encrypted PDF cannot be decrypted: {exc}") from exc

    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            pages.append("")

    text = "\n".join(pages).strip()
    return {"text": text, "page_count": len(reader.pages)}
