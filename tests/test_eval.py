import importlib.util
import io
import json
import re
import sys
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from docintel.evaluation import (
    compare_fields,
    deterministic_sample_indices,
    field_metrics,
    normalize_ground_truth,
)
from docintel.pipeline.spreadsheet import parse as parse_spreadsheet

_SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "docintel_evaluation_cli",
    Path(__file__).resolve().parents[1] / "scripts" / "eval.py",
)
if _SCRIPT_SPEC is None or _SCRIPT_SPEC.loader is None:
    raise RuntimeError("Could not load evaluation CLI for corpus-generation tests.")
_EVALUATION_CLI = importlib.util.module_from_spec(_SCRIPT_SPEC)
sys.modules[_SCRIPT_SPEC.name] = _EVALUATION_CLI
_SCRIPT_SPEC.loader.exec_module(_EVALUATION_CLI)


def test_compare_excludes_unknown_ground_truth_fields() -> None:
    predicted = {"invoice_number": "INV-1", "supplier_name": "Acme"}
    truth = {"invoice_number": "INV-1", "supplier_name": None, "total": None}

    assert compare_fields(predicted, truth) == (1, 1)


@pytest.mark.parametrize("predicted_value", [None, "not-a-number", float("inf")])
def test_compare_counts_invalid_numeric_predictions_as_incorrect(predicted_value: object) -> None:
    assert compare_fields({"total": predicted_value}, {"total": 25.0}) == (0, 1)


def test_compare_accepts_numeric_strings_within_tolerance() -> None:
    assert compare_fields({"total": "25.0000001"}, {"total": 25.0}) == (1, 1)


def test_compare_empty_or_unlabeled_truth_has_no_accuracy_denominator() -> None:
    assert compare_fields({}, {}) == (0, 0)
    assert compare_fields({}, {"total": None}) == (0, 0)


def test_normalize_sparrow_ground_truth_to_invoice_schema() -> None:
    raw = {
        "gt_parse": {
            "header": {
                "invoice_no": "INV-17",
                "invoice_date": "10/15/2012",
                "seller": "Seller Ltd",
                "client": "Buyer LLC",
            },
            "summary": {
                "total_net_worth": "$1,234.50",
                "total_vat": "$123.45",
                "total_gross_worth": "$1,357.95",
            },
        }
    }

    assert normalize_ground_truth("katanaml-org/invoices-donut-data-v1", raw) == {
        "invoice_number": "INV-17",
        "invoice_date": "2012-10-15",
        "supplier_name": "Seller Ltd",
        "customer_name": "Buyer LLC",
        "subtotal": 1234.5,
        "tax": 123.45,
        "total": 1357.95,
        "currency": None,
    }


def test_normalize_portuguese_annotations_preserves_unsupported_null_fields() -> None:
    raw = {
        "company": "Comércio",
        "date": "2020-11-04",
        "total": "12,20",
        "iva_amount": "2,28",
        "invoice_number": "FS A / 42402",
        "nif_buyer": "121653897",
    }

    result = normalize_ground_truth("Francisco-Cruz/InvoicesReceiptsPT", raw)

    assert result == {
        "invoice_number": "FS A / 42402",
        "invoice_date": "2020-11-04",
        "supplier_name": "Comércio",
        "customer_name": None,
        "subtotal": None,
        "tax": 2.28,
        "total": 12.2,
        "currency": None,
    }


def test_normalize_malformed_or_unlabeled_source_does_not_invent_values() -> None:
    assert set(normalize_ground_truth("katanaml-org/invoices-donut-data-v1", "not-json").values()) == {
        None
    }
    assert set(
        normalize_ground_truth("Shubhal829/high-quality-invoice-images-for-ocr", {"image": "x"}).values()
    ) == {None}


def test_deterministic_sample_indices_are_stable_and_bounded() -> None:
    first = deterministic_sample_indices("source", total=50, count=8, seed=7)

    assert first == deterministic_sample_indices("source", total=50, count=8, seed=7)
    assert len(set(first)) == 8
    assert first == sorted(first)
    with pytest.raises(ValueError, match="only 3"):
        deterministic_sample_indices("source", total=3, count=4, seed=7)


def test_field_metrics_only_include_labeled_source_cases() -> None:
    metrics = field_metrics(
        [
            {
                "case_type": "labeled",
                "ground_truth": {"invoice_number": "INV-1", "total": None},
                "predicted": {"invoice_number": "INV-1"},
            },
            {
                "case_type": "realism",
                "ground_truth": {"invoice_number": None},
                "predicted": {"invoice_number": "INV-1"},
            },
            {
                "case_type": "generated_format",
                "ground_truth": {"invoice_number": "INV-1"},
                "predicted": {},
            },
        ]
    )

    assert metrics["aggregate"] == {"correct": 1, "total": 1, "accuracy": 1.0}
    assert metrics["fields"]["total"] == {"correct": 0, "total": 0, "accuracy": None}


def test_compare_normalizes_dates_before_comparison() -> None:
    """Equivalent dates in different formats count as a match."""
    assert compare_fields({"invoice_date": "02/23/2020"}, {"invoice_date": "2020-02-23"}) == (1, 1)
    assert compare_fields({"invoice_date": "2020-02-23"}, {"invoice_date": "02/23/2020"}) == (1, 1)


def test_compare_rejects_date_vs_non_date() -> None:
    """A date must not match a non-date string."""
    assert compare_fields({"invoice_date": "not-a-date"}, {"invoice_date": "2020-02-23"}) == (0, 1)
    assert compare_fields({"invoice_date": "2020-02-23"}, {"invoice_date": "not-a-date"}) == (0, 1)


def test_compare_rejects_invalid_date_on_both_sides() -> None:
    """Two unparseable date-like strings use exact match, not date normalization."""
    assert compare_fields({"invoice_date": "hello"}, {"invoice_date": "world"}) == (0, 1)
    assert compare_fields({"invoice_date": "hello"}, {"invoice_date": "hello"}) == (1, 1)


def test_compare_entity_names_with_address_do_not_match() -> None:
    """Ground truth embedding an address in the name does not match a name-only prediction."""
    assert compare_fields(
        {"supplier_name": "Kirk-Green"},
        {"supplier_name": "Kirk-Green 7858 Christopher Pass Wellsside, KY 32616"},
    ) == (0, 1)


def test_compare_confirmed_absence_counts_false_positive() -> None:
    """A non-null prediction on a confirmed-absent field is incorrect."""
    truth = {"customer_name": None}
    predicted = {"customer_name": "Consumidor final"}
    assert compare_fields(predicted, truth, confirmed_absence=frozenset({"customer_name"})) == (0, 1)


def test_compare_confirmed_absence_counts_correct_absence() -> None:
    """A null prediction on a confirmed-absent field is correct."""
    truth = {"customer_name": None}
    predicted = {"customer_name": None}
    assert compare_fields(predicted, truth, confirmed_absence=frozenset({"customer_name"})) == (1, 1)


def test_field_metrics_excludes_unknown_nulls_from_denominator() -> None:
    """Unknown-null GT fields are excluded from accuracy denominators."""
    metrics = field_metrics(
        [
            {
                "case_type": "labeled",
                "ground_truth": {"invoice_number": "INV-1", "customer_name": None},
                "predicted": {"invoice_number": "INV-1", "customer_name": "Consumidor final"},
                "source": "invoicesreceiptspt",
            }
        ]
    )
    assert metrics["fields"]["customer_name"]["total"] == 0
    assert metrics["fields"]["customer_name"]["accuracy"] is None
    assert metrics["fields"]["invoice_number"]["total"] == 1
    assert metrics["fields"]["invoice_number"]["correct"] == 1
    assert metrics["unknown_null_predictions"] == {"customer_name": 1}


def test_field_metrics_confirmed_absence_includes_in_denominator() -> None:
    """Confirmed-absence null fields are included in accuracy denominators."""
    from docintel.evaluation import SOURCE_CONFIRMED_ABSENCE

    SOURCE_CONFIRMED_ABSENCE["confirmed-source"] = frozenset({"customer_name"})
    try:
        metrics = field_metrics(
            [
                {
                    "case_type": "labeled",
                    "ground_truth": {"customer_name": None},
                    "predicted": {"customer_name": "Consumidor final"},
                    "source": "confirmed-source",
                }
            ]
        )
        assert metrics["fields"]["customer_name"]["total"] == 1
        assert metrics["fields"]["customer_name"]["correct"] == 0
        assert metrics["fields"]["customer_name"]["accuracy"] == 0.0
        assert metrics["unknown_null_predictions"] == {}
    finally:
        del SOURCE_CONFIRMED_ABSENCE["confirmed-source"]


def test_prepare_generates_labeled_formats_and_expected_edge_case_labels(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _EVALUATION_CLI.SOURCES["sparrow"]
    image_buffer = io.BytesIO()
    Image.new("RGB", (32, 48), "white").save(image_buffer, format="JPEG")
    ground_truth = {
        "invoice_number": "INV-1",
        "invoice_date": "2024-01-02",
        "supplier_name": "Seller",
        "customer_name": "Buyer",
        "subtotal": 10.0,
        "tax": 1.0,
        "total": 11.0,
        "currency": None,
    }
    monkeypatch.setattr(
        _EVALUATION_CLI,
        "_verify_source_license",
        lambda _: {
            "repo_id": source["id"],
            "revision": "test-revision",
            "license": "mit",
            "access": "offline test",
            "source_url": "https://example.invalid",
        },
    )
    monkeypatch.setattr(
        _EVALUATION_CLI,
        "_fetch_examples",
        lambda *args: [
            {
                "sample_id": "sample-1",
                "image_name": "invoice.jpg",
                "image_bytes": image_buffer.getvalue(),
                "ground_truth": ground_truth,
            }
        ],
    )
    output = tmp_path / "corpus"

    _EVALUATION_CLI.prepare_corpus(output, ["sparrow"], {"sparrow": 1}, seed=17)

    manifest = json.loads((output / "manifest.json").read_text())
    entries = {Path(entry["file"]).name: entry for entry in manifest["files"]}
    assert all((output / entry["file"]).is_file() for entry in manifest["files"])
    assert PdfReader(output / "fixtures/sample-1/invoice-multipage.pdf").get_num_pages() == 2
    with Image.open(output / "fixtures/sample-1/invoice-multipage.tiff") as image:
        assert image.n_frames == 2
    workbook = parse_spreadsheet(output / "fixtures/sample-1/invoice.xlsx")
    assert len(workbook["sheets"]) == 2
    assert workbook["sheets"][0]["rows"][2][0] == "invoice_number"
    assert entries["invoice-mismatch.xlsx"]["expected"]["validation_codes"] == [
        "calculation_mismatch"
    ]
    assert entries["invoice.xlsx"]["expected"]["validation_codes"] == []
    assert entries["duplicate.jpg"]["expected"]["validation_codes"] == ["duplicate_invoice"]
    assert entries["wrong-extension.pdf"]["expected"]["upload"] == "rejected"
    assert entries["empty.csv"]["expected"]["upload"] == "rejected"
    assert entries["password-protected.pdf"]["expected"]["processing"] == "failed"
    assert manifest["unsupported_generation"]["xls"]
    assert (output / entries["corrupt.xlsx"]["file"]).read_bytes().startswith(b"PK\x03\x04")


def test_runner_separates_metrics_and_does_not_hide_expected_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    files = [
        ("invoice.jpg", "labeled", {}, {"invoice_number": "INV-1", "total": 10.0}),
        ("match.xlsx", "validation_control", {"validation_codes": []}, {}),
        (
            "mismatch.xlsx",
            "negative_validation",
            {"validation_codes": ["calculation_mismatch"]},
            {},
        ),
        ("duplicate.jpg", "duplicate_detection", {"validation_codes": ["duplicate_invoice"]}, {}),
        ("corrupt.pdf", "failure", {"processing": "failed"}, {}),
        ("wrong.pdf", "wrong_extension", {"upload": "rejected"}, {}),
        ("stress.pdf", "stress", {"processing": "complete"}, {}),
    ]
    entries = []
    for name, case_type, expected, truth in files:
        (tmp_path / name).write_bytes(b"fixture")
        entries.append(
            {
                "id": name,
                "file": name,
                "source": "test-source",
                "case_type": case_type,
                "expected": expected,
                "ground_truth": truth,
            }
        )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"sources": {"test-source": {}}, "files": entries}))
    uploaded: dict[str, tuple[str, str]] = {}
    next_id = 0

    def fake_api_request(url: str, *, method: str = "GET", body=None, **kwargs):
        nonlocal next_id
        if method == "POST":
            filename = re.search(rb'filename="([^"]+)"', body).group(1).decode()
            if filename == "wrong.pdf":
                raise _EVALUATION_CLI.EvaluationError("API returned HTTP 400: rejected")
            next_id += 1
            doc_id, job_id = f"doc-{next_id}", f"job-{next_id}"
            uploaded[job_id] = (doc_id, filename)
            return {"document_ids": [doc_id], "job_ids": [job_id]}
        if "/api/jobs/" in url:
            job_id = url.rsplit("/", 1)[-1]
            _, filename = uploaded[job_id]
            return {"status": "failed" if filename == "corrupt.pdf" else "complete"}
        document_id = url.rsplit("/", 1)[-1]
        filename = next(name for doc_id, name in uploaded.values() if doc_id == document_id)
        codes = {
            "mismatch.xlsx": ["calculation_mismatch"],
            "duplicate.jpg": ["duplicate_invoice"],
        }.get(filename, [])
        return {
            "document": {"status": "done"},
            "extraction": {"invoice_number": "INV-1", "total": 10.0},
            "validation_errors": [{"code": code} for code in codes],
        }

    monkeypatch.setattr(_EVALUATION_CLI, "_api_request", fake_api_request)

    summary, results = _EVALUATION_CLI.run_evaluation(
        manifest_path,
        "http://example.test",
        timeout=1,
        poll_interval=0.001,
    )

    assert len(results) == 6
    assert summary["unexpected_failures"] == 0
    assert summary["processing_failures"] == 1
    assert summary["upload_rejections"] == 1
    assert summary["field_accuracy"]["aggregate"]["accuracy"] == 1.0
    assert summary["planted_validation_cases"]["matched"] == 2
    assert summary["duplicate_detection_cases"]["matched"] == 1
    assert summary["stress"]["executed"] is False
