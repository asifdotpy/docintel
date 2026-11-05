# Decisions (locked)

This file locks the choices so later agents do not re-pick them. Source: `docs/PACKAGES.md` and the Care Guide brief. Change only by editing this file in a dedicated task.

## Project identity

- Project name: `docintel`
- Working directory: `interview/docintel`
- Assessment: Care Guide AI Engineer (AI-Powered Document Intelligence System)
- Deadline: 2026-11-08 (five days from the 2026-11-03 email)

## Language and runtime

- Backend: Python 3.12, packaged as `docintel` under `src/`.
- Frontend: Next.js (App Router) + Tailwind + react-dropzone, under `apps/web/`.
- One backend language only. No Node backend, no Python sidecar.

## HTTP API

- FastAPI + Pydantic v2. Typed JSON and auto OpenAPI at `/docs`.
- Uvicorn. Background work does NOT run in FastAPI background tasks; it runs on the arq worker.

## Database

- PostgreSQL 16 with pgvector (`pgvector/pgvector:pg16`).
- One store for rows, JSON, full text, and vectors. No Mongo, no Elasticsearch, no Qdrant.
- SQLAlchemy 2 (async) + Alembic migrations + psycopg.
- Schema lives in `src/docintel/models.py` (T02). Migrations in `alembic/versions/`.

## Queue

- arq + Redis. Async worker with retries. Task T09.

## Document processing

- Digital PDF text: pypdf (reads text layer, no model download).
- OCR: pytesseract + pdf2image + Pillow. System packages `tesseract-ocr` and `poppler-utils` (installed in T05).
- Spreadsheets: pandas + openpyxl + xlrd (xlsx, xls, csv).
- No Docling, no Unstructured. The text-vs-OCR branch must stay visible.

## AI extraction

- openai SDK pointed at Gemini's OpenAI-compatible endpoint (https://generativelanguage.googleapis.com/v1beta/openai/). Gemini free tier for testing. Structured outputs.
- Model from `GEMINI_MODEL` (default `gemini-3.5-flash-lite`). Re-check Google AI docs before T07.
- `EXTRACTOR=fake` skips the network for tests; `EXTRACTOR=gemini` calls the API.
- Extracted fields are fixed: Invoice Number, Invoice Date, Supplier Name, Customer Name, Subtotal, Tax, Total, Currency, Line Items. Do not invent missing values (null).

## Semantic search

- fastembed (`BAAI/bge-small-en-v1.5`, 384 dims) behind the `search` extra.
- `uv sync --group dev` for T01-T09; `uv sync --group dev --extra search` for T10.
- Default test run does not download the model.

## Tests

- pytest + httpx + fpdf2 (synthetic PDFs). Tests under `tests/`.

## Frontend allowed packages

- Only new npm package allowed: react-dropzone. Everything else is already in Next.js/Tailwind.

## Storage

- Uploaded files on local disk under `DATA_DIR` (default `./data/uploads`). No object storage.

## API shape (high level)

- Base URL `http://localhost:8000`. Prefix `/api`.
- Uploads enqueue a job; status polled by job id; results fetched by document id.
- Search: keyword filters + semantic search (vector).
- Corrections and reprocess endpoints per document.

## Non-goals

- No user accounts / auth. No second database. No custom OCR or xlsx parser.
- No paid vector DB.
