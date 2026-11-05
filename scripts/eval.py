from __future__ import annotations

import json
import time
from pathlib import Path

from fpdf import FPDF

from docintel.config import settings
from docintel.extract import extract_invoice
from docintel.pipeline.pdf_text import extract as pdf_text_extract

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "eval"
DATASET = EVAL_DIR / "dataset.json"
RESULTS = EVAL_DIR / "results.json"
REPORT = ROOT / "docs" / "eval" / "report.md"


def _ensure_pdf(path: Path, entry: dict) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if entry.get("corrupt"):
        path.write_text("not a pdf")
        return
    gt = entry["ground_truth"]
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, f"Invoice {gt['invoice_number']} Date {gt['invoice_date']}")
    pdf.cell(0, 10, f"Supplier: {gt['supplier_name']} Customer: {gt['customer_name']}")
    pdf.cell(0, 10, f"Subtotal {gt['subtotal']:.2f} Tax {gt['tax']:.2f} Total {gt['total']:.2f} {gt['currency']}")
    pdf.output(str(path))


def _compare(predicted: dict, truth: dict) -> tuple[int, int]:
    total = 0
    correct = 0
    for key, expected in truth.items():
        total += 1
        actual = predicted.get(key)
        if isinstance(expected, float):
            if actual is not None and abs(float(actual) - expected) < 1e-6:
                correct += 1
        else:
            if actual == expected:
                correct += 1
    return correct, total


def main() -> None:
    dataset = json.loads(DATASET.read_text())
    results = []
    successes = 0
    failures = 0
    total_fields = 0
    correct_fields = 0
    latencies: list[float] = []

    for entry in dataset:
        path = EVAL_DIR / entry["file"]
        _ensure_pdf(path, entry)
        start = time.perf_counter()
        status = "success"
        error = None
        predicted: dict = {}
        try:
            if entry.get("corrupt"):
                # Force a failure path: parse should raise on corrupt input.
                pdf_text_extract(path)
                raise ValueError("expected corrupt file to fail parsing")
            parsed = pdf_text_extract(path)
            text = parsed.get("text", "")
            invoice = extract_invoice(text)
            predicted = invoice.model_dump()
            successes += 1
        except Exception as exc:  # noqa: BLE001
            status = "failure"
            error = str(exc)
            failures += 1
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)

        if status == "success":
            c, t = _compare(predicted, entry["ground_truth"])
            correct_fields += c
            total_fields += t
        else:
            c, t = 0, len(entry["ground_truth"])

        results.append(
            {
                "id": entry["id"],
                "file": entry["file"],
                "status": status,
                "error": error,
                "latency_s": round(elapsed, 4),
                "field_accuracy": (c / t) if t else 0.0,
                "predicted": predicted,
            }
        )

    n = len(dataset)
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    accuracy = (correct_fields / total_fields) if total_fields else 0.0

    summary = {
        "samples": n,
        "successes": successes,
        "failures": failures,
        "success_rate": successes / n if n else 0.0,
        "field_accuracy": accuracy,
        "avg_latency_s": round(avg_latency, 4),
        "extractor": settings.extractor,
    }

    RESULTS.write_text(json.dumps({"summary": summary, "results": results}, indent=2))

    lines = [
        "# Evaluation Report",
        "",
        f"- Samples: {n}",
        f"- Extractor: {settings.extractor}",
        f"- Successes: {successes} ({summary['success_rate']:.0%})",
        f"- Failures: {failures}",
        f"- Field accuracy: {accuracy:.0%} ({correct_fields}/{total_fields})",
        f"- Avg latency: {avg_latency:.4f}s",
        "",
        "## Per-sample",
        "",
        "| id | status | latency (s) | field accuracy |",
        "|----|--------|-------------|----------------|",
    ]
    for r in results:
        lines.append(f"| {r['id']} | {r['status']} | {r['latency_s']} | {r['field_accuracy']:.0%} |")
    lines.append("")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines))

    print(json.dumps(summary, indent=2))
    print(f"Report written to {REPORT}")


if __name__ == "__main__":
    main()
