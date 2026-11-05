from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass

from ..extract.schema import Invoice


@dataclass
class ValidationIssue:
    code: str
    field: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


REQUIRED_FIELDS = ("invoice_number", "invoice_date", "supplier_name", "total")
NUMERIC_TOLERANCE = 0.01


def validate(
    invoice: Invoice,
    existing_keys: Iterable[tuple[str | None, str | None]] | None = None,
) -> list[dict[str, str]]:
    issues: list[ValidationIssue] = []

    for field in REQUIRED_FIELDS:
        value = getattr(invoice, field)
        if value is None or value == "":
            issues.append(
                ValidationIssue(
                    code="missing_field",
                    field=field,
                    message=f"Required field '{field}' is missing.",
                )
            )

    for field in ("subtotal", "tax", "total"):
        value = getattr(invoice, field)
        if value is not None and value < 0:
            issues.append(
                ValidationIssue(
                    code="invalid_number",
                    field=field,
                    message=f"'{field}' must not be negative.",
                )
            )

    if (
        invoice.subtotal is not None
        and invoice.tax is not None
        and invoice.total is not None
        and abs((invoice.subtotal + invoice.tax) - invoice.total) > NUMERIC_TOLERANCE
    ):
        issues.append(
            ValidationIssue(
                code="calculation_mismatch",
                field="total",
                message="subtotal + tax does not equal total.",
            )
        )

    if invoice.invoice_number and invoice.supplier_name:
        key = (invoice.invoice_number, invoice.supplier_name)
        if existing_keys is not None and key in set(existing_keys):
            issues.append(
                ValidationIssue(
                    code="duplicate_invoice",
                    field="invoice_number",
                    message="Duplicate invoice for this supplier.",
                )
            )

    return [issue.to_dict() for issue in issues]


def validation_key(invoice: Invoice) -> tuple[str | None, str | None]:
    return (invoice.invoice_number, invoice.supplier_name)
