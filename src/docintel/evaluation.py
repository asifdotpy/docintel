from __future__ import annotations

import json
import math
import random
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

INVOICE_FIELDS = (
    "invoice_number",
    "invoice_date",
    "supplier_name",
    "customer_name",
    "subtotal",
    "tax",
    "total",
    "currency",
)

SOURCE_LABEL_MAPPINGS = {
    "katanaml-org/invoices-donut-data-v1": {
        "invoice_number": "gt_parse.header.invoice_no",
        "invoice_date": "gt_parse.header.invoice_date",
        "supplier_name": "gt_parse.header.seller",
        "customer_name": "gt_parse.header.client",
        "subtotal": "gt_parse.summary.total_net_worth",
        "tax": "gt_parse.summary.total_vat",
        "total": "gt_parse.summary.total_gross_worth",
        "currency": None,
    },
    "Francisco-Cruz/InvoicesReceiptsPT": {
        "invoice_number": "invoice_number",
        "invoice_date": "date",
        "supplier_name": "company",
        "customer_name": None,
        "subtotal": None,
        "tax": "iva_amount",
        "total": "total",
        "currency": None,
    },
    "Shubhal829/high-quality-invoice-images-for-ocr": {
        "invoice_number": None,
        "invoice_date": None,
        "supplier_name": None,
        "customer_name": None,
        "subtotal": None,
        "tax": None,
        "total": None,
        "currency": None,
    },
}


def _nested_value(value: Mapping[str, Any], path: str | None) -> Any:
    if path is None:
        return None
    result: Any = value
    for part in path.split("."):
        if not isinstance(result, Mapping):
            return None
        result = result.get(part)
    return result


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        if not isinstance(value, str):
            return None
        cleaned = "".join(char for char in value.strip() if char.isdigit() or char in ".,-")
        if not cleaned:
            return None
        if "," in cleaned and "." not in cleaned:
            cleaned = cleaned.replace(",", ".")
        elif "," in cleaned and "." in cleaned:
            decimal_separator = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
            grouping_separator = "." if decimal_separator == "," else ","
            cleaned = cleaned.replace(grouping_separator, "").replace(decimal_separator, ".")
        try:
            number = float(cleaned)
        except (ValueError, OverflowError):
            return None
    return number if math.isfinite(number) else None


def _iso_date(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    for date_format in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), date_format).date().isoformat()
        except ValueError:
            pass
    return value.strip()


def normalize_ground_truth(source_id: str, raw: Any) -> dict[str, Any]:
    """Map available source annotations to the fixed app schema without guessing."""
    normalized = dict.fromkeys(INVOICE_FIELDS)
    mapping = SOURCE_LABEL_MAPPINGS.get(source_id)
    if mapping is None or raw is None:
        return normalized
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return normalized
    if not isinstance(raw, Mapping):
        return normalized
    for field in INVOICE_FIELDS:
        path = mapping[field]
        value = _nested_value(raw, path) if path and "not exposed" not in path else None
        if field in {"subtotal", "tax", "total"}:
            normalized[field] = _number(value)
        elif field == "invoice_date":
            normalized[field] = _iso_date(value)
        elif isinstance(value, str) and value.strip():
            normalized[field] = value.strip()
    return normalized


def deterministic_sample_indices(source_id: str, total: int, count: int, seed: int) -> list[int]:
    if total < 0 or count < 0:
        raise ValueError("total and count must not be negative")
    if count > total:
        raise ValueError(f"requested {count} samples but the source has only {total}")
    generator = random.Random(f"{source_id}:{seed}")
    return sorted(generator.sample(range(total), count))


def compare_fields(
    predicted: Mapping[str, object],
    truth: Mapping[str, object],
) -> tuple[int, int]:
    total = 0
    correct = 0
    for key, expected in truth.items():
        if expected is None:
            continue
        total += 1
        actual = predicted.get(key)
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            try:
                matches = actual is not None and abs(float(actual) - expected) < 1e-6
            except (TypeError, ValueError, OverflowError):
                matches = False
            if matches:
                correct += 1
        elif actual == expected:
            correct += 1
    return correct, total


def field_metrics(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = {field: {"correct": 0, "total": 0} for field in INVOICE_FIELDS}
    for record in records:
        if record.get("case_type") != "labeled":
            continue
        truth = record.get("ground_truth") or {}
        predicted = record.get("predicted") or {}
        for field in INVOICE_FIELDS:
            expected = truth.get(field)
            if expected is None:
                continue
            counts[field]["total"] += 1
            correct, _ = compare_fields({field: predicted.get(field)}, {field: expected})
            counts[field]["correct"] += correct
    for item in counts.values():
        item["accuracy"] = item["correct"] / item["total"] if item["total"] else None
    total = sum(item["total"] for item in counts.values())
    correct = sum(item["correct"] for item in counts.values())
    return {
        "fields": counts,
        "aggregate": {
            "correct": correct,
            "total": total,
            "accuracy": correct / total if total else None,
        },
    }

