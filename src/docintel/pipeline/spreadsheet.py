"""Parse spreadsheets (xlsx, xls, csv) into normalized tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


class SpreadsheetParseError(Exception):
    """Raised when a spreadsheet cannot be read."""


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _dataframe_to_rows(frame: pd.DataFrame) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for record in frame.itertuples(index=False, name=None):
        rows.append([_normalize_value(v) for v in record])
    return rows


def _sheet_text(name: str, rows: list[list[Any]]) -> str:
    lines = [name]
    for row in rows:
        lines.append(" | ".join("" if v is None else str(v) for v in row))
    return "\n".join(lines).strip()


def parse(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext == ".csv":
            frame = pd.read_csv(p, header=None, dtype=object, keep_default_na=True)
            rows = _dataframe_to_rows(frame)
            sheets = [{"name": "Sheet1", "rows": rows, "text": _sheet_text("Sheet1", rows)}]
            return {"sheets": sheets, "text": sheets[0]["text"]}
        if ext in {".xlsx", ".xls"}:
            engine = "openpyxl" if ext == ".xlsx" else "xlrd"
            frames = pd.read_excel(p, sheet_name=None, header=None, dtype=object, engine=engine)
            sheets = []
            for sheet_name, frame in frames.items():
                rows = _dataframe_to_rows(frame)
                sheets.append(
                    {
                        "name": str(sheet_name),
                        "rows": rows,
                        "text": _sheet_text(str(sheet_name), rows),
                    }
                )
            combined = "\n\n".join(s["text"] for s in sheets).strip()
            return {"sheets": sheets, "text": combined}
    except SpreadsheetParseError:
        raise
    except Exception as exc:
        raise SpreadsheetParseError(f"Cannot parse spreadsheet: {exc}") from exc

    raise SpreadsheetParseError(f"Unsupported spreadsheet format: {ext}")
