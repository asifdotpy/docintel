# DocIntel — Assessment Submission Status

**Assessment:** AI-Powered Document Intelligence System  
**Deadline stated in the email:** November 8, 2026, 3:39 AM  
**Repository:** `https://github.com/asifdotpy/docintel`

## Executive status

The application is implemented and was re-verified end to end on 2026-11-07:
upload → background job → extraction → validation → document retrieval, plus
keyword/semantic search, manual correction, and duplicate detection. The backend
test suite passes (92 tests), ruff is clean, and the Next.js production build
succeeds.

The evaluation evidence remains small: the labeled benchmark contains four
source-labeled invoices and 23 labeled fields. Report the measured numbers with
that limitation; do not describe them as a broad or production-scale accuracy
claim.

The walkthrough video, CV, professional references, and portfolio are
candidate-provided items and still need to be prepared/attached separately.

## Verified on 2026-11-07

- PostgreSQL/Redis started with `docker compose up -d`; Alembic migration
  `0001_initial` applied.
- Live API + arq worker processed real uploads through to completed jobs.
- Corrupt files were accepted and handled without crashing the worker; empty
  files and wrong-extension uploads were rejected with HTTP 400.
- Semantic search returned HTTP 200 after fixing a `numpy.float32` JSON
  serialization error.
- Browser access from the Next.js frontend was unblocked by adding CORS
  middleware and a configurable `CORS_ORIGINS` setting.
- The upload UI now polls job status and links to the completed document.
- Frontend pages load and the production build completes.
- `.env` is not tracked by Git; API keys are supplied locally via environment
  variables.

## Fresh evaluation run (2026-11-07)

Clean run: local corpus, live Gemini `gemini-3.5-flash-lite`, one API process,
one worker, truncated database, empty Redis queue, 300-second per-case timeout.

- Cases attempted: 35
- Completed jobs: 31/35 (88.6%); 31/33 accepted uploads (93.9%)
- Failed jobs: 1; upload rejections: 2 (expected); timeouts: 1
- **Labeled extraction: 14/23 fields correct (60.9%) across 4 invoices**
- Per-field: invoice number 2/4; invoice date 3/4; supplier 0/4; customer 0/2;
  subtotal 2/2; tax 3/3; total 4/4; currency has no labeled values.
- Processing by format: JPG 5/5, TIFF 4/4, PDF 11/12, CSV 4/5, XLSX 7/9.
- Processing by source: Francisco-Cruz 14/14; katanaml 17/21.
- Planted validation cases matched: 2/6; duplicate detection matched: 1/1.
- Latency: mean 29.26s; p50 15.52s; p95 151.78s. The p95 is inflated by one
  300s timeout and one 151.8s labeled-document job; the median is more
  representative.
- 1000-page stress test: not run.

Dataset sources:

- `katanaml-org/invoices-donut-data-v1` (MIT): 2 selected invoices.
- `Francisco-Cruz/InvoicesReceiptsPT` (Apache-2.0): 2 selected invoices.

See [the evaluation report](./docs/eval/report.md) and
[machine-readable results](./eval/results.json).

## Assessment deliverables checklist

| Deliverable | Status |
|---|---|
| 1. Source repository | Available at the repository URL above. Commit/push the current working tree before submission. |
| 2. README and setup instructions | Present in `README.md`, including Docker services, migration, API, worker, frontend, embedding warm-up, and extractor configuration. |
| 3. Architecture diagram and database schema | Recorded in `docs/architecture.md`, SQLAlchemy models, and Alembic migrations. |
| 4. Working backend and frontend | Verified end to end on 2026-11-07: upload, job processing, extraction, validation, retrieval, search, and correction. Frontend production build passes. |
| 5. PDF/image/Excel/CSV pipelines | Implemented and exercised by tests plus the evaluation corpus (PDF, JPG, TIFF, PNG, XLSX, XLS, CSV, multi-page/multi-sheet, corrupt/empty files). |
| 6. Automated tests and results | `PYTHONPATH=src uv run pytest -q` → **92 passed**. `uv run ruff check .` → clean. |
| 7. Evaluation report | Present in `docs/eval/report.md` with the fresh run above and explicit small-sample limitations. |
| 8. Recorded walkthrough | **Pending candidate action.** `docs/walkthrough.md` is a script, not a recording. |
| 9. AI prompts/disclosure | Present in `docs/AI_DISCLOSURE.md` and the extraction prompt source. |

## Before replying to the email

1. Commit and push the current changes so the public repository matches what was
   tested.
2. Record the requested 3–5 minute application walkthrough.
3. Prepare the updated CV with education, experience, and two professional
   references using official institutional/organizational email addresses.
4. Attach/link the portfolio and completed assessment.
5. Reply All to the original email thread and keep `apply@careguidebd.com`
   included. Do not claim production-scale accuracy or unverified metrics.

## Known environment note

`npm run build` succeeds, but ESLint prints a plugin-load error caused by a
corrupted local `node_modules` (`Cannot find module './Call'`). A clean
`npm ci` in `apps/web` resolves it; it does not block the production build.
