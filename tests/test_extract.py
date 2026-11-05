
import pytest

from docintel.config import settings
from docintel.extract import Invoice, extract_invoice


def test_fake_extraction_returns_invoice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "extractor", "fake")
    invoice = extract_invoice("some invoice text")
    assert invoice.invoice_number == "INV-FAKE-001"
    assert invoice.subtotal == 100.0
    assert invoice.tax == 10.0
    assert invoice.total == 110.0
    assert invoice.currency == "USD"
    assert len(invoice.line_items) == 1
    assert invoice.line_items[0].amount == 100.0


def test_invoice_schema_defaults_none() -> None:
    inv = Invoice()
    assert inv.invoice_number is None
    assert inv.line_items == []


def test_unknown_extractor_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTOR", "nope")
    # settings already loaded; override attribute
    monkeypatch.setattr(settings, "extractor", "nope")
    with pytest.raises(ValueError):
        extract_invoice("text")


def test_fake_mode_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "extractor", "fake")
    inv = extract_invoice("anything")
    assert inv.total == 110.0
