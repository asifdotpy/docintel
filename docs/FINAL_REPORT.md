# Final Report — Care Guide AI Engineer Assessment (DocIntel)

## Status

All 19 tracked tasks are complete. The backend suite passes (92 tests), ruff is
clean, the frontend production build succeeds, and the application was verified
end to end on 2026-11-07 with live Gemini extraction.

## What was built

- Backend: FastAPI (Python 3.12), async SQLAlchemy, PostgreSQL + pgvector, arq
  worker on Redis.
- Pipelines: digital-PDF text (pypdf), OCR (Tesseract + pdf2image), spreadsheets
  (pandas: XLSX/XLS/CSV), Gemini extraction (OpenAI-compatible,
  `gemini-3.5-flash-lite`), validation (missing fields, bad numbers,
  subtotal + tax = total, duplicates), fastembed 384-dim semantic search.
- APIs: multi-file upload, job status, document get/PATCH correction/reprocess,
  keyword/semantic/hybrid search.
- Frontend: Next.js 15 App Router — drag-and-drop upload with job progress,
  document inspector, manual correction, and search.
- Tests: 92 covering parsing, OCR, spreadsheets, extraction, validation,
  failures, worker, tracker, models, health/CORS, uploads, documents, and search.
- Docs: decisions, acceptance criteria, architecture, walkthrough script, AI
  disclosure, evaluation report, and README.

## Verification and fixes after review

- Fixed semantic-search HTTP 500 caused by `numpy.float32` JSON serialization.
- Added CORS middleware/config so the browser frontend can call the API.
- Fixed upload UX so the UI polls job status and links to the completed document.
- Added LLM client timeout/retry and moved blocking parse/OCR/extraction work off
  the event loop; raised the worker job timeout for slow OCR/extraction cases.
- Documented embedding warm-up and `uv sync --all-extras` / `EXTRACTOR=gemini`
  setup in `README.md`.
- Corrected the AI disclosure model name and dataset description.
- Re-ran the evaluation against a clean database/queue.

## Evaluation

Fresh clean run (2026-11-07, 300s timeout, live Gemini):

- 31/35 cases completed (88.6%); 31/33 accepted uploads (93.9%).
- 4 labeled fields strongest: subtotal 2/2, tax 3/3, total 4/4.
- Overall labeled field accuracy: 14/23 (60.9%) across four invoices.
- Latency: mean 29.26s, p50 15.52s, p95 151.78s (p95 inflated by one timeout
  and one slow document).
- Validation controls: 2/6 matched; duplicate detection: 1/1.

The labeled benchmark is small (four invoices, 23 fields). These results show the
pipeline works end to end; they are not a production-scale accuracy claim.

## How to run

1. `docker compose up -d`
2. `PYTHONPATH=src uv run alembic upgrade head`
3. `PYTHONPATH=src uv run uvicorn docintel.main:app --port 8000`
4. `PYTHONPATH=src uv run arq docintel.worker.WorkerSettings`
5. `cd apps/web && npm install && npm run dev`

Tests: `PYTHONPATH=src uv run pytest -q`  
Lint: `uv run ruff check .`  
Evaluation: see `docs/eval/report.md` and `eval/results.json`.

## Model

Gemini `gemini-3.5-flash-lite` via
`https://generativelanguage.googleapis.com/v1beta/openai/`. Set
`EXTRACTOR=fake` for offline tests.

## Remaining (candidate action)

- Record the 3–5 minute walkthrough video per `docs/walkthrough.md`.
- Prepare the CV with education, experience, and two professional references
  using official institutional/organizational email addresses.
- Attach/link the portfolio.
- Push the current changes and submit via Reply All to the original email by
  November 8, 2026, 3:39 AM, keeping `apply@careguidebd.com` included.
- Optional: run `npm ci` in `apps/web` to clear the local ESLint plugin corruption
  (the production build already succeeds).
