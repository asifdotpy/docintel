# Final Report — Care Guide AI Engineer Assessment (DocIntel)

## Status
All 17 tasks complete. 67/67 tests pass. Ruff clean. Frontend builds. End-to-end verified with live Gemini.

## What was built
- Backend: FastAPI (Python 3.12), async SQLAlchemy, Postgres + pgvector, arq worker on Redis.
- Pipelines: digital PDF text (pypdf), OCR (Tesseract + pdf2image), spreadsheets (pandas: xlsx/xls/csv), Gemini extraction (OpenAI-compatible, gemini-3.5-flash-lite), validation (missing fields, bad numbers, subtotal+tax=total, duplicates), fastembed 384-dim semantic search.
- APIs: upload (multi-file), job status, document get/PATCH corrections/reprocess, keyword/semantic/hybrid search.
- Frontend: Next.js 15 App Router — drag-and-drop upload, inspector, manual correction, search.
- Tests: 67 (parsing, OCR, spreadsheets, extraction, validation, failures, worker, tracker, models, health, uploads, documents, search).
- Eval: 4 varied invoices + 1 corrupt case → 75% success, 100% field accuracy, 1.41s avg latency.
- Docs: DECISIONS, ACCEPTANCE, BRIEF, architecture, walkthrough, AI disclosure, README.

## Key fixes after review
- PATCH re-validates and replaces validation errors; updates status.
- Worker clears stale errors; None extraction → needs_review; (None,None) duplicate guard.
- Eval no longer circular (varied ground truth + corrupt failure case).
- Frontend build passes; AGENTS.md/README updated.

## How to run
1. `docker compose up -d`
2. `PYTHONPATH=src uv run alembic upgrade head`
3. `PYTHONPATH=src uv run uvicorn docintel.main:app --port 8000`
4. `PYTHONPATH=src uv run arq docintel.worker.WorkerSettings`
5. `cd apps/web && npm run dev`
Tests: `PYTHONPATH=src uv run pytest -q`
Eval: `PYTHONPATH=src uv run python scripts/eval.py`

## Model
Gemini gemini-3.5-flash-lite via https://generativelanguage.googleapis.com/v1beta/openai/. xAI removed. Set EXTRACTOR=fake for offline tests.

## Remaining (user action)
- Record 3–5 min walkthrough video per docs/walkthrough.md.
- Submit portfolio, CV with references, and assessment via Reply All to original email by Nov 8 3:39 AM.
- Optional: clean up node_modules ESLint corruption (build unaffected).
