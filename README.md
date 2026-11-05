# DocIntel — Automated Document Intelligence System

Care Guide AI Engineer assessment: process invoices, receipts, scanned PDFs, images,
Excel, and CSV. Parse -> extract -> validate -> store -> search. Backend is Python
(FastAPI); frontend is Next.js.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy (async), arq, Postgres + pgvector, Redis
- Frontend: Next.js 15 (App Router), Tailwind
- OCR: Tesseract + pdf2image/Poppler
- Embeddings: fastembed (BAAI/bge-small-en-v1.5)
- Extraction: OpenAI-compatible LLM (Gemini) with a deterministic fake mode for offline runs

See `docs/DECISIONS.md` for the full rationale.

## Setup

1. Prerequisites: Python 3.12+, Node 20+, Docker, Tesseract, Poppler.

   ```bash
   sudo apt-get install -y tesseract-ocr poppler-utils
   ```

2. Start infra:

   ```bash
   docker compose up -d
   ```

3. Backend:

   ```bash
   uv sync
   cp .env.example .env   # fill GEMINI_API_KEY to use real extraction
   PYTHONPATH=src uv run uvicorn docintel.main:app --reload --port 8000
   ```

4. Worker (separate terminal):

   ```bash
   PYTHONPATH=src uv run arq docintel.worker.WorkerSettings
   ```

5. Frontend:

   ```bash
   cd apps/web && npm install && npm run dev
   ```

   Open http://localhost:3000.

## Tests

```bash
PYTHONPATH=src uv run pytest -q
```

## Evaluation

```bash
PYTHONPATH=src uv run python scripts/eval.py
```

Report: `docs/eval/report.md`. Results: `eval/results.json`.

## API

- `POST /api/documents/upload` — multi-file upload, enqueues jobs
- `GET /api/jobs/{id}` — job status
- `GET /api/documents/{id}` — document + extraction + validation errors
- `PATCH /api/documents/{id}` — manual correction (re-validates)
- `POST /api/documents/{id}/reprocess` — re-run pipeline
- `GET /api/search` — keyword/semantic/hybrid search

## Environment variables

See `.env.example`.

## Tracker

Task board: `python3 scripts/task.py list`. Brief: `docs/BRIEF.md`. Acceptance map: `docs/ACCEPTANCE.md`.
