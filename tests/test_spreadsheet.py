from pathlib import Path

import pandas as pd
import pytest

from docintel.pipeline.spreadsheet import SpreadsheetParseError, parse


def test_parse_csv(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("invoice,total\nINV-1,25.00\nINV-2,10.00\n", encoding="utf-8")
    result = parse(path)
    assert len(result["sheets"]) == 1
    assert result["sheets"][0]["name"] == "Sheet1"
    assert result["sheets"][0]["rows"][0] == ["invoice", "total"]
    assert "INV-1" in result["text"]


def test_parse_csv_utf8(tmp_path: Path) -> None:
    path = tmp_path / "utf8.csv"
    path.write_text("name,city\nCafé,Dhaka\n", encoding="utf-8")
    result = parse(path)
    assert "Café" in result["text"]


def test_parse_xlsx_multi_sheet(tmp_path: Path) -> None:
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_excel(writer, sheet_name="Sheet1", index=False)
        pd.DataFrame({"x": [5]}).to_excel(writer, sheet_name="Sheet2", index=False)
    result = parse(path)
    assert len(result["sheets"]) == 2
    names = [s["name"] for s in result["sheets"]]
    assert "Sheet1" in names and "Sheet2" in names
    sheet1 = next(s for s in result["sheets"] if s["name"] == "Sheet1")
    assert sheet1["rows"][0] == ["a", "b"]
    assert sheet1["rows"][1] == [1, 3]


def test_parse_empty_sheet(tmp_path: Path) -> None:
    path = tmp_path / "empty.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame().to_excel(writer, sheet_name="Empty", index=False)
        pd.DataFrame({"a": [1]}).to_excel(writer, sheet_name="Data", index=False)
    result = parse(path)
    empty = next(s for s in result["sheets"] if s["name"] == "Empty")
    assert empty["rows"] == []


def test_parse_corrupt_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.xlsx"
    path.write_bytes(b"not an xlsx")
    with pytest.raises(SpreadsheetParseError):
        parse(path)


def test_parse_csv_empty_raises(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(SpreadsheetParseError):
        parse(path)


def test_parse_unsupported_raises(tmp_path: Path) -> None:
    path = tmp_path / "data.txt"
    path.write_text("hi")
    with pytest.raises(SpreadsheetParseError):
        parse(path)
