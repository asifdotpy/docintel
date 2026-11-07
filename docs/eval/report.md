# DocIntel end-to-end evaluation

This report describes the most recent clean end-to-end run (2026-11-07), using
the local evaluation corpus, a live Gemini extractor
(`gemini-3.5-flash-lite`), one API process, one worker, a truncated database and
an empty Redis queue. The runner used a 300-second per-case timeout.

## Run summary

- Cases attempted: 35
- Completed jobs: 31
- Failed jobs: 1
- Upload rejections: 2 (both expected)
- Timeouts: 1
- Completed cases: 31/35 (88.6%); among 33 accepted uploads, 31/33 jobs
  completed (93.9%).
- Unexpected validation outcomes: 4 completed validation controls did not match
  their planted expectation; 2/6 planted validation cases matched overall.
- Labeled field accuracy: 60.9% (14/23)
- Mean latency: 29.26s; p50/p95 latency: 15.52s / 151.78s
- Source image/OCR cases completed: 4/4
- Duplicate detection cases matched: 1/1
- 1000-page stress test: not run.

The p95 latency is inflated by one 300s timeout and one 151.8s labeled-document
job. The median (15.52s) is more representative of typical processing.

## Selected source samples

| Source | Samples |
|---|---:|
| Francisco-Cruz/InvoicesReceiptsPT | 2 |
| katanaml-org/invoices-donut-data-v1 | 2 |

## Per-field accuracy

Comparison semantics (as of T17):
- Numeric values use tolerance comparison (±1e-6).
- Dates are normalized to ISO format before comparison; equivalent dates in
  different formats (e.g. "02/23/2020" vs "2020-02-23") count as a match.
  Invalid or ambiguous dates are not guessed into a match.
- String fields use exact match; ground-truth values that embed addresses in
  name fields (e.g. "Kirk-Green 7858 Christopher Pass ...") do not match
  name-only predictions. No address stripping is applied.
- Unknown-null ground-truth fields are excluded from accuracy denominators.
  Confirmed-absence null fields are included; a non-null prediction on a
  confirmed-absent field counts as a false positive.
- These are four source-labeled documents and 23 labeled fields, not 35 labeled
  invoices. Generated-format, validation, duplicate, and failure cases exercise
  processing paths but do not add labeled invoices.
- Predictions on unknown-null fields, excluded from accuracy, were observed for
  `customer_name` (1), `subtotal` (1), and `currency` (4). These are not counted
  as confirmed-absence false positives because the sources do not document those
  nulls as confirmed absence.

| Field | Correct | Labeled | Accuracy |
|---|---:|---:|---:|
| invoice_number | 2 | 4 | 50.0% |
| invoice_date | 3 | 4 | 75.0% |
| supplier_name | 0 | 4 | 0.0% |
| customer_name | 0 | 2 | 0.0% |
| subtotal | 2 | 2 | 100.0% |
| tax | 3 | 3 | 100.0% |
| total | 4 | 4 | 100.0% |
| currency | 0 | 0 | n/a |

## Processing success by source

| Source | Completed | Total |
|---|---:|---:|
| Francisco-Cruz/InvoicesReceiptsPT | 14 | 14 |
| katanaml-org/invoices-donut-data-v1 | 17 | 21 |

## Processing success by format

| Format | Completed | Total |
|---|---:|---:|
| .csv | 4 | 5 |
| .jpg | 5 | 5 |
| .pdf | 11 | 12 |
| .tiff | 4 | 4 |
| .xlsx | 7 | 9 |

## Per-case

| ID | Type | Status | Latency (s) | Error |
|---|---|---|---:|---|
| sparrow-000191-original | labeled | complete | 45.9575 |  |
| sparrow-000191-invoice | labeled_format | complete | 20.6002 |  |
| sparrow-000191-invoice-multipage | generated_format | complete | 25.3624 |  |
| sparrow-000191-invoice-multipage | generated_format | complete | 26.5353 |  |
| sparrow-000191-invoice | generated_format | complete | 3.1023 |  |
| sparrow-000191-invoice | validation_control | complete | 6.1795 |  |
| sparrow-000191-invoice-mismatch | negative_validation | complete | 4.1554 |  |
| sparrow-000271-original | labeled | complete | 26.4788 |  |
| sparrow-000271-invoice | labeled_format | complete | 15.5665 |  |
| sparrow-000271-invoice-multipage | generated_format | complete | 28.8734 |  |
| sparrow-000271-invoice-multipage | generated_format | complete | 37.3449 |  |
| sparrow-000271-invoice | generated_format | complete | 3.1053 |  |
| sparrow-000271-invoice | validation_control | timeout | 300.0315 | Job did not finish within 300s. |
| sparrow-000271-invoice-mismatch | negative_validation | complete | 74.3081 |  |
| 20210215_165944-original | labeled | complete | 151.7763 |  |
| 20210215_165944-invoice | labeled_format | complete | 15.5235 |  |
| 20210215_165944-invoice-multipage | generated_format | complete | 63.4325 |  |
| 20210215_165944-invoice-multipage | generated_format | complete | 29.5089 |  |
| 20210215_165944-invoice | generated_format | complete | 5.2086 |  |
| 20210215_165944-invoice | validation_control | complete | 4.1727 |  |
| 20210215_165944-invoice-mismatch | negative_validation | complete | 4.1871 |  |
| 20210323_172107-original | labeled | complete | 20.9483 |  |
| 20210323_172107-invoice | labeled_format | complete | 14.5605 |  |
| 20210323_172107-invoice-multipage | generated_format | complete | 24.8889 |  |
| 20210323_172107-invoice-multipage | generated_format | complete | 32.0697 |  |
| 20210323_172107-invoice | generated_format | complete | 4.2305 |  |
| 20210323_172107-invoice | validation_control | complete | 4.2665 |  |
| 20210323_172107-invoice-mismatch | negative_validation | complete | 6.5315 |  |
| sparrow-000191-duplicate | duplicate_detection | complete | 18.088 |  |
| sparrow-000191-corrupt | failure | complete | 1.1431 |  |
| sparrow-000191-empty | failure | complete | 3.312 |  |
| sparrow-000191-wrong-extension | wrong_extension | upload_rejected | 0.0732 | API returned HTTP 400: {"detail":"File content does not look like a PDF."} |
| sparrow-000191-corrupt | failure | failed | 1.1285 | Cannot parse spreadsheet: File is not a zip file |
| sparrow-000191-empty | empty | upload_rejected | 0.0352 | API returned HTTP 400: {"detail":"Uploaded file is empty."} |
| sparrow-000191-password-protected | failure | complete | 1.2881 |  |

## Interpretation

- The pipeline handles all requested input families in this corpus, including
  digital PDFs, scanned images, TIFF, CSV, XLSX, multi-page documents, corrupt
  files, empty files, and wrong-extension uploads.
- Structured totals (subtotal, tax, total) are extracted reliably on this small
  labeled set; supplier and customer names are the weakest fields because the
  labels include address text that exact-match comparison rejects.
- One validation-control case timed out at 300s, and four validation controls
  produced different validation codes than planted. Treat validation behavior as
  partially verified rather than fully correct.
- The labeled benchmark is only four invoices / 23 fields. These numbers are
  evidence that the pipeline works end to end, not a production accuracy claim.
  Do not tune on these samples and present them as an independent test set.
