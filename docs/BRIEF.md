# Assessment brief

Source: the Care Guide AI Engineer assessment emailed to the candidate. This file is the requirement list. Decisions about how to meet it are in `docs/DECISIONS.md`.

## Scenario

A company processes about 1,000 pages a day: invoices, receipts, scanned PDFs, images, Excel sheets, and CSV files. People currently extract details and cross-check them by hand.

Build an automated document intelligence system that processes, extracts, validates, and queries those documents through a backend API and a web UI.

## Tasks

1. **Document processing.** Accept PDF, JPG, PNG, TIFF, XLSX, XLS, and CSV. Use text extraction for digital PDFs, OCR for scans and images, and a parser for spreadsheets. Handle multi-page PDFs, multiple sheets, poor image quality, and corrupted files.
2. **AI extraction.** Fields: Invoice Number, Invoice Date, Supplier Name, Customer Name, Subtotal, Tax, Total, Currency, and Line Items. Return JSON. Do not invent missing values.
3. **Validation.** Flag missing fields, bad numbers, calculation mismatches (`subtotal + tax = total`), and duplicate invoices. Anomalous records go to manual review.
4. **Backend API.** Upload, processing status, extracted results, search, manual corrections, and reprocessing of failed jobs. OCR and AI work run on a queue.
5. **Database and search.** Store metadata, extracted text, structured JSON, validation errors, and processing history. Support keyword filters and semantic search.
6. **Frontend.** React or Next.js: multi-file drag-and-drop upload, live progress, an inspector for extracted fields and validation errors, manual correction, and search over processed documents.
7. **Tests and evaluation.** Automated tests for parsing, OCR, spreadsheets, extraction, validation, and failures. A labeled dataset with accuracy, latency, success rate, and failure rate.

## Deliverables

- Git repository with source
- README and setup instructions
- Architecture diagram and database schema
- Working API and frontend
- Pipelines for PDF, image, Excel, and CSV
- Automated tests and results
- Evaluation report
- 3–5 minute walkthrough video
- AI prompts and a development disclosure

## Suggested stack in the brief

The brief allows Node/Nest or Python, Postgres or Mongo, Redis/BullMQ, and a vector database. This repo locks one choice in `docs/DECISIONS.md` so later agents do not spend a session re-picking it.
