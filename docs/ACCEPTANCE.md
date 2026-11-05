# Acceptance map

Maps each line of the assessment brief (`docs/BRIEF.md`) to the task that covers it. Use this to confirm nothing is missed before T16.

| Brief line | Task |
|---|---|
| Scenario: ~1,000 pages/day, invoices/receipts/scans/images/Excel/CSV | T01-T09 (pipeline) |
| Task 1 Document processing: accept PDF/JPG/PNG/TIFF/XLSX/XLS/CSV | T04, T05, T06 |
| Text extraction for digital PDFs | T04 |
| OCR for scans and images | T05 |
| Parser for spreadsheets | T06 |
| Multi-page PDFs, multiple sheets, poor quality, corrupted files | T05, T06, T14 |
| Task 2 AI extraction: fixed fields, JSON, no invented values | T07 |
| Task 3 Validation: missing fields, bad numbers, subtotal+tax=total, duplicates | T08 |
| Anomalous records to manual review | T08, T11, T13 |
| Task 4 Backend API: upload, status, results, search, corrections, reprocess | T03, T11 |
| Background queue for OCR/AI | T03, T09 |
| Task 5 Database & search: metadata, text, JSON, errors, history | T02 |
| Keyword filters + semantic search | T10 |
| Task 6 Frontend: drag-and-drop multi-upload, progress, inspector, corrections, search | T12, T13 |
| Task 7 Tests: parsing, OCR, spreadsheets, extraction, validation, failures | T04-T08, T14 |
| Labeled dataset + accuracy/latency/success/failure | T15 |
| Deliverable: Git repo + source | all |
| Deliverable: README + setup | T16 |
| Deliverable: Architecture diagram + DB schema | T02, T16 |
| Deliverable: Working API + frontend | T01-T13 |
| Deliverable: Pipelines | T04-T06 |
| Deliverable: Automated tests + results | T14, T15 |
| Deliverable: Evaluation report | T15 |
| Deliverable: 3-5 min walkthrough video | T16 |
| Deliverable: AI prompts + dev disclosure | T07, T16 |

## Coverage check

Every task id in `board.json` must have a brief in `docs/tasks/`. Every brief must list "Create or edit" paths matching the task's `owns`. Tracker test enforces existence of briefs.
