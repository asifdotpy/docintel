from pathlib import Path

import pytest

from docintel.pipeline import ocr, router
from docintel.pipeline.pdf_text import PdfTextError
from docintel.pipeline.pdf_text import extract as pdf_extract
from docintel.pipeline.spreadsheet import SpreadsheetParseError
from docintel.pipeline.spreadsheet import parse as ss_parse

BAD = Path(__file__).parent / "fixtures" / "bad"


def test_corrupt_pdf_raises_controlled() -> None:
    with pytest.raises(PdfTextError):
        pdf_extract(BAD / "corrupt.pdf")


def test_corrupt_spreadsheet_raises_controlled() -> None:
    with pytest.raises(SpreadsheetParseError):
        ss_parse(BAD / "corrupt.xlsx")


def test_corrupt_csv_raises_controlled() -> None:
    with pytest.raises(SpreadsheetParseError):
        ss_parse(BAD / "corrupt.csv")


def test_empty_csv_raises_controlled() -> None:
    with pytest.raises(SpreadsheetParseError):
        ss_parse(BAD / "empty.csv")


def test_corrupt_image_returns_empty() -> None:
    # OCR image should not raise; returns empty string on failure.
    result = ocr.image(BAD / "corrupt.png")
    assert result == ""


def test_empty_image_returns_empty() -> None:
    result = ocr.image(BAD / "empty.png")
    assert result == ""


def test_empty_pdf_ocr_returns_error_dict() -> None:
    result = ocr.pdf(BAD / "empty.pdf")
    assert isinstance(result, dict)
    assert result.get("error") is True


def test_router_detect_corrupt_pdf_falls_back_to_ocr() -> None:
    # router.detect tries pdf_text.extract; on failure returns pdf_ocr (no exception)
    assert router.detect(BAD / "corrupt.pdf") == "pdf_ocr"


def test_router_detect_empty_pdf() -> None:
    # empty pdf has no text layer -> pdf_ocr
    assert router.detect(BAD / "empty.pdf") == "pdf_ocr"


def test_router_detect_corrupt_image() -> None:
    assert router.detect(BAD / "corrupt.png") == "image"


def test_router_detect_corrupt_spreadsheet() -> None:
    assert router.detect(BAD / "corrupt.xlsx") == "spreadsheet"


def test_router_unsupported_extension_raises() -> None:
    with pytest.raises(ValueError):
        router.detect(BAD / "nope.txt")
