import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from docintel.pipeline import ocr

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
POPPLER_AVAILABLE = shutil.which("pdftoppm") is not None


@pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract not installed")
def test_ocr_image(tmp_path: Path) -> None:
    img = Image.new("RGB", (400, 100), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 24)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    draw.text((10, 30), "HELLO 123", fill="black", font=font)
    path = tmp_path / "text.png"
    img.save(path)

    text = ocr.image(path)
    assert "HELLO" in text.upper() or "123" in text


@pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract not installed")
def test_ocr_image_missing_file_returns_empty() -> None:
    # Should not crash
    result = ocr.image("/tmp/does-not-exist.png")
    assert result == ""


@pytest.mark.skipif(
    not (TESSERACT_AVAILABLE and POPPLER_AVAILABLE),
    reason="tesseract or poppler not installed",
)
def test_ocr_pdf(tmp_path: Path) -> None:
    # Build a simple PDF with text via fpdf, then OCR its rendered pages.
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Invoice total 42")
    path = tmp_path / "scan.pdf"
    pdf.output(str(path))

    result = ocr.pdf(path)
    assert result["page_count"] == 1
    assert result["error"] is False
    # OCR may or may not read perfectly; ensure no crash
    assert isinstance(result["text"], str)
