from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from fpdf import FPDF
from PIL import Image
from pypdf import PdfReader, PdfWriter

from docintel.evaluation import (
    INVOICE_FIELDS,
    SOURCE_LABEL_MAPPINGS,
    compare_fields,
    deterministic_sample_indices,
    field_metrics,
    normalize_ground_truth,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "eval" / "local"
MANIFEST_NAME = "manifest.json"
SOURCES = {
    "sparrow": {
        "id": "katanaml-org/invoices-donut-data-v1",
        "license": "mit",
        "attribution": (
            "Katana ML, Sparrow Invoice Dataset; original source: Kozłowski and "
            "Weichbroth (2021), Mendeley Data, DOI 10.17632/tnj49gpmtz.2."
        ),
        "kind": "hub_rows",
        "split": "train",
    },
    "invoicesreceiptspt": {
        "id": "Francisco-Cruz/InvoicesReceiptsPT",
        "license": "apache-2.0",
        "attribution": (
            "Francisco Cruz, InvoicesReceiptsPT, Hugging Face dataset repository; "
            "also published at Zenodo records 7213544 and 6371710."
        ),
        "kind": "pt_files",
    },
}
USER_AGENT = "docintel-local-evaluation/1.0"
HTTP_TIMEOUT = 60
MAX_PAGE_SIZE = 100


class EvaluationError(RuntimeError):
    pass


def _request(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        raise EvaluationError(f"Request failed for {url}: {error}") from error


def _cached_download(cache_dir: Path, cache_key: str, url: str) -> bytes:
    destination = cache_dir / cache_key
    if destination.exists():
        return destination.read_bytes()
    content = _request(url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return content


def _json_request(url: str) -> Any:
    try:
        return json.loads(_request(url))
    except json.JSONDecodeError as error:
        raise EvaluationError(f"Invalid JSON response from {url}") from error


def _quote_repo_path(path: str) -> str:
    return urllib.parse.quote(path, safe="/")


def _verify_source_license(source: dict[str, Any]) -> dict[str, Any]:
    repo_id = source["id"]
    info = _json_request(f"https://huggingface.co/api/datasets/{repo_id}")
    card_data = info.get("cardData") or {}
    license_id = card_data.get("license")
    if license_id != source["license"]:
        raise EvaluationError(
            f"{repo_id} license changed or is not declared as expected "
            f"(expected {source['license']!r}, found {license_id!r}); review the source "
            "license and update the source catalog before downloading."
        )
    if info.get("gated") or info.get("private"):
        raise EvaluationError(f"{repo_id} is gated or private; access was not authorized.")
    revision = info.get("sha")
    if not isinstance(revision, str) or not revision:
        raise EvaluationError(f"{repo_id} did not provide an immutable source revision.")
    return {
        "repo_id": repo_id,
        "revision": revision,
        "license": license_id,
        "access": "public, ungated Hugging Face repository",
        "source_url": f"https://huggingface.co/datasets/{repo_id}",
    }


def _fetch_hub_rows(repo_id: str, split: str, count: int, seed: int) -> list[dict[str, Any]]:
    base = "https://datasets-server.huggingface.co"
    split_data = _json_request(
        f"{base}/splits?dataset={urllib.parse.quote(repo_id, safe='')}"
    )
    available = [item["split"] for item in split_data.get("splits", [])]
    if split not in available:
        raise EvaluationError(f"Split {split!r} is unavailable for {repo_id}: {available}")
    query = urllib.parse.urlencode(
        {"dataset": repo_id, "config": "default", "split": split, "offset": 0, "length": 1}
    )
    first = _json_request(f"{base}/rows?{query}")
    total = int(first.get("num_rows_total", 0))
    indices = deterministic_sample_indices(repo_id, total, count, seed)
    if count == 0:
        return []
    selected: dict[int, dict[str, Any]] = {}
    page_offsets = sorted({(index // MAX_PAGE_SIZE) * MAX_PAGE_SIZE for index in indices})
    for offset in page_offsets:
        query = urllib.parse.urlencode(
            {
                "dataset": repo_id,
                "config": "default",
                "split": split,
                "offset": offset,
                "length": min(MAX_PAGE_SIZE, total - offset),
            }
        )
        page = _json_request(f"{base}/rows?{query}")
        for item in page.get("rows", []):
            selected[int(item["row_idx"])] = item["row"]
    missing = [index for index in indices if index not in selected]
    if missing:
        raise EvaluationError(f"Dataset server omitted selected rows for {repo_id}: {missing}")
    return [{"index": index, "row": selected[index]} for index in indices]


def _tree_files(repo_id: str, directory: str, revision: str) -> list[str]:
    url = (
        f"https://huggingface.co/api/datasets/{repo_id}/tree/{revision}/"
        f"{_quote_repo_path(directory)}?recursive=true&expand=false&limit=1000"
    )
    files = _json_request(url)
    if not isinstance(files, list):
        raise EvaluationError(f"Unexpected file listing for {repo_id}/{directory}")
    return [
        item["path"]
        for item in files
        if item.get("type") == "file" and isinstance(item.get("path"), str)
    ]


def _fetch_pt_examples(
    repo_id: str,
    count: int,
    seed: int,
    revision: str,
    cache_dir: Path,
) -> list[dict[str, Any]]:
    images = _tree_files(repo_id, "1_Images", revision)
    annotations = _tree_files(repo_id, "2_Annotations_Json", revision)
    annotations_by_stem = {Path(path).stem: path for path in annotations}
    paired = sorted(
        (path for path in images if Path(path).stem in annotations_by_stem),
        key=lambda path: Path(path).name,
    )
    try:
        indices = deterministic_sample_indices(repo_id, len(paired), count, seed)
    except ValueError as error:
        raise EvaluationError(str(error)) from error
    examples = []
    for index in indices:
        image_path = paired[index]
        annotation_path = annotations_by_stem[Path(image_path).stem]
        sample_id = Path(image_path).stem
        prefix = f"{repo_id.replace('/', '-')}/{revision}/{sample_id}"
        try:
            raw_annotation = json.loads(
                _cached_download(
                    cache_dir,
                    f"{prefix}.json",
                    f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/"
                    f"{_quote_repo_path(annotation_path)}",
                )
            )
        except json.JSONDecodeError as error:
            raise EvaluationError(f"Invalid annotation JSON: {annotation_path}") from error
        image_url = (
            f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/"
            f"{_quote_repo_path(image_path)}"
        )
        examples.append(
            {
                "index": index,
                "sample_id": sample_id,
                "image_bytes": _cached_download(
                    cache_dir, f"{prefix}{Path(image_path).suffix.lower()}", image_url
                ),
                "image_name": Path(image_path).name,
                "raw_ground_truth": raw_annotation,
            }
        )
    return examples


def _fetch_examples(
    source_name: str,
    source: dict[str, Any],
    count: int,
    seed: int,
    revision: str,
    cache_dir: Path,
) -> list[dict[str, Any]]:
    if source["kind"] == "pt_files":
        examples = _fetch_pt_examples(source["id"], count, seed, revision, cache_dir)
        for example in examples:
            example["ground_truth"] = normalize_ground_truth(
                source["id"], example.pop("raw_ground_truth")
            )
        return examples

    examples = []
    try:
        selected_rows = _fetch_hub_rows(source["id"], source["split"], count, seed)
    except ValueError as error:
        raise EvaluationError(str(error)) from error
    for item in selected_rows:
        row = item["row"]
        image = row.get("image") or {}
        image_url = image.get("src")
        if not isinstance(image_url, str):
            raise EvaluationError(f"Missing image URL in {source['id']} row {item['index']}")
        parsed_url = urllib.parse.urlparse(image_url)
        if parsed_url.scheme != "https" or parsed_url.hostname not in {
            "huggingface.co",
            "datasets-server.huggingface.co",
        }:
            raise EvaluationError(f"Refusing unexpected dataset image URL: {image_url}")
        examples.append(
            {
                "index": item["index"],
                "sample_id": f"{source_name}-{item['index']:06d}",
                "image_bytes": _cached_download(
                    cache_dir,
                    f"{source['id'].replace('/', '-')}/{revision}/{item['index']:06d}"
                    f"{Path(parsed_url.path).suffix.lower()}",
                    image_url,
                ),
                "image_name": Path(parsed_url.path).name or "source-image.jpg",
                "ground_truth": normalize_ground_truth(source["id"], row.get("ground_truth")),
            }
        )
    return examples


def _invoice_row(ground_truth: dict[str, Any], *, mismatch: bool = False) -> list[Any]:
    fields = list(INVOICE_FIELDS)
    values = [ground_truth.get(field) for field in fields]
    if (
        mismatch
        and ground_truth.get("subtotal") is not None
        and ground_truth.get("tax") is not None
        and ground_truth.get("total") is not None
    ):
        values[fields.index("total")] = ground_truth["total"] + 1
    return [fields, values]


def _write_spreadsheets(directory: Path, ground_truth: dict[str, Any]) -> None:
    fields, values = _invoice_row(ground_truth)
    mismatch_fields, mismatch_values = _invoice_row(ground_truth, mismatch=True)
    csv_buffer = io.StringIO()
    csv_writer = csv.writer(csv_buffer)
    csv_writer.writerow(fields)
    csv_writer.writerow(values)
    (directory / "invoice.csv").write_text(csv_buffer.getvalue(), encoding="utf-8")
    with pd.ExcelWriter(directory / "invoice.xlsx", engine="openpyxl") as writer:
        preamble = ["Generated evaluation fixture"] + [None] * (len(fields) - 1)
        pd.DataFrame([preamble, [None] * len(fields), fields, values]).to_excel(
            writer,
            sheet_name="Invoice",
            header=False,
            index=False,
        )
        pd.DataFrame([["Source sample", "Ground truth-derived fixture"]]).to_excel(
            writer, sheet_name="Notes", header=False, index=False
        )
    with pd.ExcelWriter(directory / "invoice-mismatch.xlsx", engine="openpyxl") as writer:
        pd.DataFrame([mismatch_fields, mismatch_values]).to_excel(
            writer, sheet_name="Invoice", header=False, index=False
        )


def _write_pdf_from_image(image_path: Path, destination: Path, pages: int = 1) -> None:
    pdf = FPDF(unit="mm", format="A4")
    for _ in range(pages):
        pdf.add_page()
        pdf.image(str(image_path), x=8, y=8, w=194, h=281, keep_aspect_ratio=True)
    pdf.output(str(destination))


def _write_empty_pdf(destination: Path) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.output(str(destination))


def _write_stress_pdf(destination: Path, page_count: int) -> None:
    pdf = FPDF()
    for page in range(page_count):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, f"DocIntel evaluation stress page {page + 1}")
    pdf.output(str(destination))


def _manifest_entry(
    *,
    sample: dict[str, Any],
    source: dict[str, Any],
    relative_path: str,
    case_type: str,
    ground_truth: dict[str, Any] | None = None,
    expected: dict[str, Any] | None = None,
    pair_id: str | None = None,
    pair_relation: str | None = None,
    sample_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": f"{sample_id or sample['sample_id']}-{Path(relative_path).stem}",
        "file": relative_path,
        "source": source["id"],
        "source_sample_id": sample_id or sample["sample_id"],
        "license": source["license"],
        "attribution": source["attribution"],
        "label_mapping": SOURCE_LABEL_MAPPINGS[source["id"]],
        "excluded_fields": [
            field for field in INVOICE_FIELDS if (ground_truth or {}).get(field) is None
        ],
        "case_type": case_type,
        "ground_truth": ground_truth or dict.fromkeys(INVOICE_FIELDS),
        "expected": expected or {"processing": "complete"},
        "pair_id": pair_id,
        "pair_relation": pair_relation,
    }


def prepare_corpus(
    output: Path,
    source_names: list[str],
    sample_counts: dict[str, int],
    seed: int,
    *,
    stress_pages: int = 0,
    overwrite: bool = False,
) -> dict[str, Any]:
    manifest_path = output / MANIFEST_NAME
    if manifest_path.exists() and not overwrite:
        raise EvaluationError(f"{manifest_path} already exists; choose another output or pass --overwrite.")
    if len(set(source_names)) != len(source_names):
        raise EvaluationError("source names must be unique.")
    if not sample_counts or any(count < 1 for count in sample_counts.values()):
        raise EvaluationError("each selected source must request at least one sample.")
    output.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    source_metadata = {}

    for source_name in source_names:
        if source_name not in SOURCES:
            raise EvaluationError(f"Unknown source {source_name!r}; choose from {sorted(SOURCES)}.")
        source = SOURCES[source_name]
        metadata = _verify_source_license(source)
        source_metadata[source["id"]] = {
            **metadata,
            "attribution": source["attribution"],
            "label_mapping": SOURCE_LABEL_MAPPINGS[source["id"]],
            "limitations": (
                "The dataset repository has paired JSON annotations; fields unsupported by the "
                "fixed app schema stay null and are excluded from exact-match accuracy."
                if source_name == "invoicesreceiptspt"
                else "Only annotated fields supported by the fixed app schema are scored."
            ),
        }
        count = sample_counts[source_name]
        examples = _fetch_examples(
            source_name,
            source,
            count,
            seed,
            metadata["revision"],
            output / "cache",
        )
        for sample in examples:
            ground_truth = sample["ground_truth"]
            sample_dir_name = re.sub(r"[^a-zA-Z0-9._-]", "-", sample["sample_id"])
            sample_dir = output / "fixtures" / sample_dir_name
            sample_dir.mkdir(parents=True, exist_ok=True)
            suffix = Path(sample["image_name"]).suffix.lower()
            if suffix not in {".jpg", ".jpeg", ".png"}:
                suffix = ".jpg"
            original = sample_dir / f"original{suffix}"
            original.write_bytes(sample["image_bytes"])
            source_case_type = "labeled" if any(v is not None for v in ground_truth.values()) else "realism"
            manifest.append(
                _manifest_entry(
                    sample=sample,
                    source=source,
                    relative_path=original.relative_to(output).as_posix(),
                    case_type=source_case_type,
                    ground_truth=ground_truth,
                )
            )

            single_pdf = sample_dir / "invoice.pdf"
            multipage_pdf = sample_dir / "invoice-multipage.pdf"
            multipage_tiff = sample_dir / "invoice-multipage.tiff"
            _write_pdf_from_image(original, single_pdf)
            _write_pdf_from_image(original, multipage_pdf, pages=2)
            with Image.open(original) as image:
                image.save(multipage_tiff, save_all=True, append_images=[image.copy()])
            pair_id = f"{sample['sample_id']}-pdf-sheet"
            for path, case in ((single_pdf, "labeled_format"), (multipage_pdf, "generated_format")):
                manifest.append(
                    _manifest_entry(
                        sample=sample,
                        source=source,
                        relative_path=path.relative_to(output).as_posix(),
                        case_type=case,
                        ground_truth=ground_truth,
                        pair_id=pair_id,
                        pair_relation="pdf",
                    )
                )
            manifest.append(
                _manifest_entry(
                    sample=sample,
                    source=source,
                    relative_path=multipage_tiff.relative_to(output).as_posix(),
                    case_type="generated_format",
                    ground_truth=ground_truth,
                )
            )

            _write_spreadsheets(sample_dir, ground_truth)
            manifest.append(
                _manifest_entry(
                    sample=sample,
                    source=source,
                    relative_path=(sample_dir / "invoice.csv").relative_to(output).as_posix(),
                    case_type="generated_format",
                    ground_truth=ground_truth,
                    pair_id=pair_id,
                    pair_relation="matched_csv",
                )
            )
            manifest.append(
                _manifest_entry(
                    sample=sample,
                    source=source,
                    relative_path=(sample_dir / "invoice.xlsx").relative_to(output).as_posix(),
                    case_type="validation_control",
                    ground_truth=ground_truth,
                    expected={"processing": "complete", "validation_codes": []},
                    pair_id=pair_id,
                    pair_relation="matched_xlsx",
                )
            )
            mismatch_expected = (
                {"processing": "complete", "validation_codes": ["calculation_mismatch"]}
                if all(ground_truth.get(field) is not None for field in ("subtotal", "tax", "total"))
                else {"processing": "complete", "validation_codes": [], "not_planted": True}
            )
            manifest.append(
                _manifest_entry(
                    sample=sample,
                    source=source,
                    relative_path=(sample_dir / "invoice-mismatch.xlsx").relative_to(output).as_posix(),
                    case_type="negative_validation",
                    ground_truth=ground_truth,
                    expected=mismatch_expected,
                    pair_id=pair_id,
                    pair_relation="mismatched_xlsx",
                )
            )

    if manifest:
        source = SOURCES[source_names[0]]
        first = manifest[0]
        sample_dir = output / Path(first["file"]).parent
        sample = {"sample_id": first["source_sample_id"]}
        reference = output / first["file"]

        duplicate_path = sample_dir / "duplicate.jpg"
        with Image.open(reference) as image:
            image.convert("RGB").save(duplicate_path, format="JPEG")
        manifest.append(
            _manifest_entry(
                sample=sample,
                source=source,
                relative_path=duplicate_path.relative_to(output).as_posix(),
                case_type="duplicate_detection",
                ground_truth=first["ground_truth"],
                expected={"processing": "complete", "validation_codes": ["duplicate_invoice"]},
                pair_id=f"{sample['sample_id']}-duplicate",
                pair_relation="duplicate",
            )
        )

        bad_pdf = sample_dir / "corrupt.pdf"
        bad_pdf.write_bytes(b"%PDF-1.4\nthis is not a valid PDF")
        empty_pdf = sample_dir / "empty.pdf"
        _write_empty_pdf(empty_pdf)
        wrong_extension = sample_dir / "wrong-extension.pdf"
        wrong_extension.write_bytes(reference.read_bytes())
        corrupt_xlsx = sample_dir / "corrupt.xlsx"
        corrupt_xlsx.write_bytes(b"PK\x03\x04corrupt workbook")
        empty_csv = sample_dir / "empty.csv"
        empty_csv.write_bytes(b"")
        encrypted_pdf = sample_dir / "password-protected.pdf"
        writer = PdfWriter()
        for page in PdfReader(str(empty_pdf)).pages:
            writer.add_page(page)
        writer.encrypt("docintel-eval")
        with encrypted_pdf.open("wb") as stream:
            writer.write(stream)
        for path, case, expected in (
            (bad_pdf, "failure", {"processing": "failed"}),
            (empty_pdf, "failure", {"processing": "complete_or_review"}),
            (wrong_extension, "wrong_extension", {"upload": "rejected"}),
            (corrupt_xlsx, "failure", {"processing": "failed"}),
            (empty_csv, "empty", {"upload": "rejected"}),
            (encrypted_pdf, "failure", {"processing": "failed"}),
        ):
            manifest.append(
                _manifest_entry(
                    sample=sample,
                    source=source,
                    relative_path=path.relative_to(output).as_posix(),
                    case_type=case,
                    expected=expected,
                )
            )

    stress_file = None
    if stress_pages:
        if stress_pages < 1:
            raise EvaluationError("stress page count must be positive.")
        stress_path = output / "stress" / f"stress-{stress_pages}-pages.pdf"
        stress_path.parent.mkdir(parents=True, exist_ok=True)
        _write_stress_pdf(stress_path, stress_pages)
        stress_file = stress_path.relative_to(output).as_posix()
        manifest.append(
            {
                "id": f"stress-{stress_pages}-pages",
                "file": stress_file,
                "source": "generated",
                "source_sample_id": None,
                "license": "generated",
                "attribution": "Generated locally by DocIntel evaluation tooling.",
                "label_mapping": {},
                "excluded_fields": list(INVOICE_FIELDS),
                "case_type": "stress",
                "ground_truth": dict.fromkeys(INVOICE_FIELDS),
                "expected": {"processing": "complete"},
                "pair_id": None,
                "pair_relation": None,
            }
        )

    payload = {
        "version": 1,
        "seed": seed,
        "samples_per_source": sample_counts,
        "sources": source_metadata,
        "unsupported_generation": {
            "xls": "Not generated: the project does not include an XLS writer dependency."
        },
        "stress_file": stress_file,
        "files": manifest,
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "manifest": manifest_path.as_posix(),
        "source_samples": sample_counts,
        "files": len(manifest),
        "stress_file": stress_file,
    }


def _multipart(file_path: Path) -> tuple[bytes, str]:
    boundary = f"docintel-{uuid.uuid4().hex}"
    content_type = "application/pdf"
    headers = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".csv": "text/csv",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
    }
    content_type = headers.get(file_path.suffix.lower(), content_type)
    content = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="{file_path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + file_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    return content, f"multipart/form-data; boundary={boundary}"


def _api_request(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
            if not isinstance(payload, dict):
                raise EvaluationError(f"API returned a non-object JSON response for {url}.")
            return payload
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise EvaluationError(f"API returned HTTP {error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise EvaluationError(f"API request failed for {url}: {error}") from error


def _run_case(
    base_url: str,
    output: Path,
    entry: dict[str, Any],
    timeout: float,
    poll_interval: float,
) -> dict[str, Any]:
    file_path = output / entry["file"]
    started = time.monotonic()
    result = {
        "id": entry["id"],
        "file": entry["file"],
        "source": entry["source"],
        "case_type": entry["case_type"],
        "ground_truth": entry.get("ground_truth") or {},
        "expected": entry.get("expected") or {},
        "status": "failure",
        "error": None,
        "predicted": {},
        "validation_errors": [],
    }
    upload_response_received = False
    try:
        body, content_type = _multipart(file_path)
        uploaded = _api_request(
            f"{base_url}/api/documents/upload",
            method="POST",
            body=body,
            content_type=content_type,
        )
        upload_response_received = True
        document_id = uploaded["document_ids"][0]
        job_id = uploaded["job_ids"][0]
        deadline = time.monotonic() + timeout
        job = {}
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            job = _api_request(
                f"{base_url}/api/jobs/{job_id}", timeout=min(30, remaining)
            )
            if job.get("status") in {"complete", "failed"}:
                break
            time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
        else:
            result["status"] = "timeout"
            result["error"] = f"Job did not finish within {timeout:g}s."
            result["latency_s"] = round(time.monotonic() - started, 4)
            return result
        result["job_status"] = job.get("status")
        if job.get("status") == "failed":
            result["status"] = "failed"
            result["error"] = job.get("error")
            result["latency_s"] = round(time.monotonic() - started, 4)
            return result
        document = _api_request(f"{base_url}/api/documents/{document_id}")
        result["document_status"] = document.get("document", {}).get("status")
        result["predicted"] = document.get("extraction") or {}
        result["validation_errors"] = document.get("validation_errors") or []
        result["status"] = "complete"
    except EvaluationError as error:
        result["error"] = str(error)
        result["status"] = (
            "upload_rejected"
            if not upload_response_received and "HTTP 400" in str(error)
            else "failure"
        )
    except (IndexError, KeyError, OSError, TypeError, ValueError) as error:
        result["error"] = f"{type(error).__name__}: {error}"
    result["latency_s"] = round(time.monotonic() - started, 4)
    return result


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def run_evaluation(
    manifest_path: Path,
    base_url: str,
    timeout: float,
    poll_interval: float,
    *,
    include_stress: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = manifest_path.resolve()
    output = manifest_path.parent.resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationError(f"Cannot read manifest {manifest_path}: {error}") from error
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise EvaluationError(f"Manifest {manifest_path} must contain a files array.")
    entries = manifest.get("files", [])
    for index, entry in enumerate(entries):
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("file"), str)
            or not isinstance(entry.get("id"), str)
            or not isinstance(entry.get("source"), str)
            or not isinstance(entry.get("case_type"), str)
        ):
            raise EvaluationError(
                f"Manifest entry {index} must include string id, file, source, and case_type fields."
            )
        entry_path = (output / entry["file"]).resolve()
        if not entry_path.is_relative_to(output):
            raise EvaluationError(f"Manifest entry {index} points outside the corpus directory.")
    if not include_stress:
        entries = [entry for entry in entries if entry.get("case_type") != "stress"]
    results = [
        _run_case(base_url.rstrip("/"), output, entry, timeout, poll_interval)
        for entry in entries
    ]
    standard_results = [result for result in results if result["case_type"] != "stress"]
    stress_results = [result for result in results if result["case_type"] == "stress"]
    for result in results:
        if result.get("status") == "complete":
            result["field_match"] = compare_fields(
                result.get("predicted") or {}, result.get("ground_truth") or {}
            )

    format_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "total": 0})
    source_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "total": 0})
    for result in standard_results:
        suffix = Path(result["file"]).suffix.lower() or "<none>"
        for grouping, key in ((format_counts, suffix), (source_counts, result["source"])):
            grouping[key]["total"] += 1
            if result["status"] == "complete":
                grouping[key]["success"] += 1

    measured = [result for result in standard_results if result["case_type"] == "labeled"]
    fields = field_metrics(measured)
    source_image_cases = [
        result
        for result in standard_results
        if result["case_type"] in {"labeled", "realism"}
    ]
    realism_only_cases = [result for result in source_image_cases if result["case_type"] == "realism"]
    validation_cases = [
        result
        for result in standard_results
        if result["case_type"] in {"negative_validation", "validation_control"}
        and result.get("expected", {}).get("validation_codes") is not None
        and not result.get("expected", {}).get("not_planted")
    ]
    validation_matches = []
    for result in validation_cases:
        actual = {item.get("code") for item in result.get("validation_errors", [])}
        expected = set(result["expected"].get("validation_codes") or [])
        validation_matches.append(actual == expected)
    duplicate_cases = [
        result for result in standard_results if result["case_type"] == "duplicate_detection"
    ]
    duplicate_matches = [
        {item.get("code") for item in result.get("validation_errors", [])}
        == set(result.get("expected", {}).get("validation_codes") or [])
        for result in duplicate_cases
    ]
    latencies = [result["latency_s"] for result in standard_results if "latency_s" in result]
    stress_latencies = [result["latency_s"] for result in stress_results if "latency_s" in result]
    unexpected = [
        result
        for result in results
        if result["status"] in {"timeout", "failure"}
        or (
            result["status"] == "failed"
            and result.get("expected", {}).get("processing")
            not in {"failed", "complete_or_review"}
        )
        or (
            result["status"] == "upload_rejected"
            and result.get("expected", {}).get("upload") != "rejected"
        )
    ]
    unexpected.extend(
        result
        for result, matched in zip(validation_cases, validation_matches, strict=True)
        if not matched and result["status"] == "complete"
    )
    unexpected.extend(
        result
        for result, matched in zip(duplicate_cases, duplicate_matches, strict=True)
        if not matched and result["status"] == "complete"
    )
    summary = {
        "samples": len(standard_results),
        "selected_source_samples": {
            source: len(
                {
                    entry.get("source_sample_id")
                    for entry in manifest.get("files", [])
                    if entry.get("source") == source
                    and entry.get("case_type") in {"labeled", "realism"}
                }
            )
            for source in manifest.get("sources", {})
        },
        "processing_successes": sum(result["status"] == "complete" for result in standard_results),
        "processing_failures": sum(result["status"] == "failed" for result in standard_results),
        "upload_rejections": sum(
            result["status"] == "upload_rejected" for result in standard_results
        ),
        "timeouts": sum(result["status"] == "timeout" for result in standard_results),
        "unexpected_failures": len(unexpected),
        "field_accuracy": fields,
        "source_image_outcomes": {
            "samples": len(source_image_cases),
            "completed": sum(result["status"] == "complete" for result in source_image_cases),
            "failed": sum(result["status"] != "complete" for result in source_image_cases),
            "unlabeled_realism_samples": len(realism_only_cases),
        },
        "processing_by_format": dict(format_counts),
        "processing_by_source": dict(source_counts),
        "planted_validation_cases": {
            "checked": len(validation_cases),
            "matched": sum(validation_matches),
            "accuracy": (
                sum(validation_matches) / len(validation_matches) if validation_matches else None
            ),
        },
        "duplicate_detection_cases": {
            "checked": len(duplicate_cases),
            "matched": sum(duplicate_matches),
            "accuracy": (
                sum(duplicate_matches) / len(duplicate_matches) if duplicate_matches else None
            ),
        },
        "latency_s": {
            "mean": sum(latencies) / len(latencies) if latencies else None,
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
        },
        "stress": {
            "executed": bool(stress_results),
            "samples": len(stress_results),
            "completed": sum(result["status"] == "complete" for result in stress_results),
            "failed": sum(result["status"] != "complete" for result in stress_results),
            "latency_s": {
                "mean": sum(stress_latencies) / len(stress_latencies) if stress_latencies else None,
                "p50": _percentile(stress_latencies, 0.50),
                "p95": _percentile(stress_latencies, 0.95),
            },
        },
    }
    return summary, results


def _write_report(path: Path, summary: dict[str, Any], results: list[dict[str, Any]]) -> None:
    fields = summary["field_accuracy"]
    lines = [
        "# DocIntel end-to-end evaluation",
        "",
        f"- Processed cases: {summary['samples']}",
        f"- Completed jobs: {summary['processing_successes']}",
        f"- Failed jobs: {summary['processing_failures']}",
        f"- Upload rejections: {summary['upload_rejections']}",
        f"- Timeouts: {summary['timeouts']}",
        f"- Unexpected failures: {summary['unexpected_failures']}",
        (
            f"- Labeled field accuracy: {fields['aggregate']['accuracy']:.1%} "
            f"({fields['aggregate']['correct']}/{fields['aggregate']['total']})"
            if fields["aggregate"]["accuracy"] is not None
            else "- Labeled field accuracy: no labeled fields in this run"
        ),
        f"- Mean latency: {summary['latency_s']['mean']!s}s",
        f"- p50/p95 latency: {summary['latency_s']['p50']!s}s / {summary['latency_s']['p95']!s}s",
        (
            f"- Source image/OCR cases completed: {summary['source_image_outcomes']['completed']}/"
            f"{summary['source_image_outcomes']['samples']}; unlabeled realism-only: "
            f"{summary['source_image_outcomes']['unlabeled_realism_samples']}"
        ),
        (
            f"- Planted validation cases detected: {summary['planted_validation_cases']['matched']}/"
            f"{summary['planted_validation_cases']['checked']}"
        ),
        (
            f"- Duplicate detection cases matched: {summary['duplicate_detection_cases']['matched']}/"
            f"{summary['duplicate_detection_cases']['checked']}"
        ),
        (
            f"- Stress cases: {summary['stress']['completed']}/{summary['stress']['samples']} "
            f"completed; mean latency {summary['stress']['latency_s']['mean']!s}s"
        ),
        "",
        "## Selected source samples",
        "",
        "| Source | Samples |",
        "|---|---:|",
    ]
    for source, count in sorted(summary["selected_source_samples"].items()):
        lines.append(f"| {source} | {count} |")
    lines.extend(
        [
            "",
            "## Per-field exact-match accuracy",
            "",
            "| Field | Correct | Labeled | Accuracy |",
            "|---|---:|---:|---:|",
        ]
    )
    for field, counts in fields["fields"].items():
        accuracy = f"{counts['accuracy']:.1%}" if counts["accuracy"] is not None else "n/a"
        lines.append(
            f"| {field} | {counts['correct']} | {counts['total']} | {accuracy} |"
        )
    lines.extend(
        [
            "",
            "## Processing success by source",
            "",
            "| Source | Completed | Total |",
            "|---|---:|---:|",
        ]
    )
    for source, count in sorted(summary["processing_by_source"].items()):
        lines.append(f"| {source} | {count['success']} | {count['total']} |")
    lines.extend(
        [
            "",
        "## Processing success by format",
        "",
        "| Format | Completed | Total |",
        "|---|---:|---:|",
        ]
    )
    for name, count in sorted(summary["processing_by_format"].items()):
        lines.append(f"| {name} | {count['success']} | {count['total']} |")
    lines.extend(["", "## Per-case", "", "| ID | Type | Status | Latency (s) | Error |", "|---|---|---|---:|---|"])
    for result in results:
        lines.append(
            f"| {result['id']} | {result['case_type']} | {result['status']} | "
            f"{result.get('latency_s', '')} | {(result.get('error') or '').replace('|', '/')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _prepare_command(args: argparse.Namespace) -> int:
    sample_counts = {name: args.samples_per_source for name in args.sources}
    overridden_counts = set()
    for specification in args.sample_count or []:
        try:
            name, raw_count = specification.split("=", 1)
            count = int(raw_count)
        except ValueError as error:
            raise EvaluationError(
                f"Invalid --sample-count {specification!r}; use SOURCE=COUNT."
            ) from error
        if name not in args.sources:
            raise EvaluationError(f"Source {name!r} is not selected by --sources.")
        if name in overridden_counts:
            raise EvaluationError(f"Sample count specified more than once for {name}.")
        sample_counts[name] = count
        overridden_counts.add(name)
    result = prepare_corpus(
        args.output.resolve(),
        args.sources,
        sample_counts,
        args.seed,
        stress_pages=args.stress_pages,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, indent=2))
    return 0


def _run_command(args: argparse.Namespace) -> int:
    summary, results = run_evaluation(
        args.manifest,
        args.api_url,
        args.timeout,
        args.poll_interval,
        include_stress=args.stress,
    )
    output = args.manifest.resolve().parent
    results_path = output / "results.json"
    report_path = output / "report.md"
    results_path.write_text(
        json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_report(report_path, summary, results)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Machine-readable results: {results_path}")
    print(f"Human-readable report: {report_path}")
    return 1 if summary["unexpected_failures"] else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and run DocIntel evaluations.")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Download a deterministic local corpus.")
    prepare.add_argument(
        "--sources",
        nargs="+",
        choices=sorted(SOURCES),
        default=["sparrow", "invoicesreceiptspt"],
    )
    prepare.add_argument("--samples-per-source", type=int, default=2)
    prepare.add_argument(
        "--sample-count",
        action="append",
        metavar="SOURCE=COUNT",
        help="Override the count for a selected source; may be repeated.",
    )
    prepare.add_argument("--seed", type=int, default=17)
    prepare.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare.add_argument("--stress-pages", type=int, default=0)
    prepare.add_argument("--overwrite", action="store_true")
    prepare.set_defaults(handler=_prepare_command)

    run = commands.add_parser("run", help="Upload fixtures to a running DocIntel app.")
    run.add_argument("--manifest", type=Path, default=DEFAULT_OUTPUT / MANIFEST_NAME)
    run.add_argument("--api-url", default="http://localhost:8000")
    run.add_argument("--timeout", type=float, default=300)
    run.add_argument("--poll-interval", type=float, default=2)
    run.add_argument("--stress", action="store_true", help="Include optional stress fixtures.")
    run.set_defaults(handler=_run_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "timeout") and (args.timeout <= 0 or args.poll_interval <= 0):
        parser.error("--timeout and --poll-interval must be positive.")
    try:
        return args.handler(args)
    except EvaluationError as error:
        print(f"Evaluation error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
