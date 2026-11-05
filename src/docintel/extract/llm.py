from __future__ import annotations

import json
import os

from openai import OpenAI

from ..config import settings
from .schema import EXTRACTION_PROMPT, Invoice


def _fake_invoice(text: str) -> Invoice:
    # Deterministic fixture used for tests and offline runs.
    return Invoice(
        invoice_number="INV-FAKE-001",
        invoice_date="2026-01-01",
        supplier_name="Fake Supplier Ltd",
        customer_name="Fake Customer Inc",
        subtotal=100.0,
        tax=10.0,
        total=110.0,
        currency="USD",
        line_items=[
            {"description": "Widget", "quantity": 2, "unit_price": 50.0, "amount": 100.0}
        ],
    )


def _gemini_extract(text: str) -> Invoice:
    client = OpenAI(
        base_url=settings.gemini_base_url,
        api_key=settings.gemini_api_key,
    )
    response = client.chat.completions.create(
        model=settings.gemini_model,
        messages=[
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "invoice",
                "schema": Invoice.model_json_schema(),
                "strict": True,
            },
        },
        temperature=0,
    )
    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    return Invoice.model_validate(data)


def extract_invoice(text: str) -> Invoice:
    mode = (settings.extractor or os.getenv("EXTRACTOR", "fake")).lower()
    if mode == "fake":
        return _fake_invoice(text)
    if mode == "gemini":
        return _gemini_extract(text)
    raise ValueError(f"Unknown extractor mode: {mode}")
