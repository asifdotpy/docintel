from typing import Any

from docintel.extract.schema import Invoice
from docintel.validate import validate, validation_key


def _valid_invoice(**overrides: Any) -> Invoice:
    data = {
        "invoice_number": "INV-1",
        "invoice_date": "2026-01-01",
        "supplier_name": "Acme",
        "customer_name": "Beta",
        "subtotal": 100.0,
        "tax": 10.0,
        "total": 110.0,
        "currency": "USD",
        "line_items": [],
    }
    data.update(overrides)
    return Invoice(**data)  # type: ignore[arg-type]


def test_valid_invoice_no_issues() -> None:
    assert validate(_valid_invoice()) == []


def test_missing_fields() -> None:
    inv = Invoice()
    issues = validate(inv)
    codes = [i["code"] for i in issues]
    assert codes.count("missing_field") >= 1
    fields = {i["field"] for i in issues if i["code"] == "missing_field"}
    assert "invoice_number" in fields
    assert "total" in fields


def test_calculation_mismatch() -> None:
    inv = _valid_invoice(total=999.0)
    issues = validate(inv)
    assert any(i["code"] == "calculation_mismatch" for i in issues)


def test_negative_total() -> None:
    inv = _valid_invoice(total=-5.0, subtotal=0, tax=0)
    # total mismatch too; check invalid_number present
    issues = validate(inv)
    assert any(i["code"] == "invalid_number" and i["field"] == "total" for i in issues)


def test_duplicate_invoice() -> None:
    inv = _valid_invoice()
    key = validation_key(inv)
    issues = validate(inv, existing_keys={key})
    assert any(i["code"] == "duplicate_invoice" for i in issues)


def test_duplicate_not_flagged_when_not_existing() -> None:
    inv = _valid_invoice()
    issues = validate(inv, existing_keys=set())
    assert not any(i["code"] == "duplicate_invoice" for i in issues)


def test_calculation_tolerance() -> None:
    inv = _valid_invoice(subtotal=100.0, tax=10.0, total=110.005)
    issues = validate(inv)
    assert not any(i["code"] == "calculation_mismatch" for i in issues)
