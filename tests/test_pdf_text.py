from pathlib import Path

import pytest
from fpdf import FPDF

from docintel.pipeline import router
from docintel.pipeline.pdf_text import PdfTextError, extract


def _make_pdf(path: Path, text: str | None = "Hello world invoice") -> Path:
    pdf = FPDF()
    pdf.add_page()
    if text:
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, text)
    pdf.output(str(path))
    return path


def test_extract_digital_pdf(tmp_path: Path) -> None:
    pdf_path = _make_pdf(tmp_path / "doc.pdf", "Invoice number 123")
    result = extract(pdf_path)
    assert result["page_count"] == 1
    assert "Invoice" in result["text"]
    assert "123" in result["text"]


def test_extract_multipage(tmp_path: Path) -> None:
    pdf = FPDF()
    for i in range(3):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, f"Page {i + 1}")
    path = tmp_path / "multi.pdf"
    pdf.output(str(path))
    result = extract(path)
    assert result["page_count"] == 3
    assert "Page 1" in result["text"]
    assert "Page 3" in result["text"]


def test_extract_empty_pdf_marks_ocr(tmp_path: Path) -> None:
    path = _make_pdf(tmp_path / "empty.pdf", None)
    result = extract(path)
    assert result["page_count"] == 1
    assert result["text"] == ""
    assert router.detect(path) == "pdf_ocr"


def test_router_detect_digital_pdf(tmp_path: Path) -> None:
    path = _make_pdf(tmp_path / "doc.pdf", "Some text")
    assert router.detect(path) == "pdf_text"


def test_router_detect_image(tmp_path: Path) -> None:
    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n")
    assert router.detect(img) == "image"


def test_router_detect_spreadsheet(tmp_path: Path) -> None:
    xlsx = tmp_path / "data.xlsx"
    xlsx.write_bytes(b"")
    assert router.detect(xlsx) == "spreadsheet"


def test_router_unsupported_raises(tmp_path: Path) -> None:
    bad = tmp_path / "file.txt"
    bad.write_text("hi")
    with pytest.raises(ValueError):
        router.detect(bad)


def test_extract_corrupt_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_text("not a pdf")
    with pytest.raises(PdfTextError):
        extract(bad)
