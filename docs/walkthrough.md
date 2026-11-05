# Walkthrough (3-5 minutes)

1. **Intro (20s)** — Problem: ~1,000 pages/day of invoices/receipts/scans/Excel/CSV extracted by hand. Goal: automated parse -> extract -> validate -> search.

2. **Architecture (40s)** — Show `docs/architecture.md`. FastAPI backend, arq worker on Redis, Postgres+pgvector, Next.js frontend. Upload -> job queued -> worker parses (text/OCR/spreadsheet) -> LLM extraction -> validation -> embed -> store.

3. **Live demo (2 min)** —
   - Drag-and-drop 3 files (digital PDF, scanned PDF, XLSX) on the upload page; show progress.
   - Open inspector: extracted fields, validation errors (e.g., subtotal+tax mismatch flagged).
   - Manual correction form updates a field and re-validates.
   - Search page: keyword "INV-FAKE" and semantic query; results link to inspector.

4. **Tests & eval (40s)** — Run `PYTHONPATH=src uv run pytest -q` (show pass count). Run `PYTHONPATH=src uv run python scripts/eval.py`; show report (`docs/eval/report.md`).

5. **Edge cases (30s)** — Corrupt PDF/image/xlsx/csv handled (no crashes), missing fields flagged, duplicates detected, reprocess endpoint for failed jobs.

6. **AI disclosure (20s)** — Mention `docs/AI_DISCLOSURE.md`: prompts, models, what was generated vs. hand-written.
