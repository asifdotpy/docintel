from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class Invoice(BaseModel):
    invoice_number: str | None = None
    invoice_date: str | None = None
    supplier_name: str | None = None
    customer_name: str | None = None
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    currency: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)


EXTRACTION_PROMPT = """You are an invoice data extraction assistant.
Extract the requested fields from the provided document text.
Return JSON matching the schema exactly. Use null for any field that is missing or unclear.
Do not invent, guess, or hallucinate values. Only use information present in the text.
For line_items, include each line item with description, quantity, unit_price, and amount.
Set currency to the ISO currency code if present (e.g. USD, EUR, BDT), else null.
"""


def invoice_json_schema() -> dict[str, Any]:
    return Invoice.model_json_schema()
