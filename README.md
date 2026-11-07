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
   uv sync --all-extras   # includes fastembed for semantic search
   cp .env.example .env
   # For real LLM extraction, set GEMINI_API_KEY and EXTRACTOR=gemini in .env.
   # The default EXTRACTOR=fake is deterministic and works offline.
   # Pre-download the embedding model once so the first document job does not
   # spend several minutes fetching it (cache defaults to the system temp dir).
   PYTHONPATH=src uv run python -c \
     "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')"
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

The local corpus preparer downloads a bounded, reproducible sample and creates
format and failure fixtures under the ignored `eval/local/` directory. It does
not add source documents or generated fixtures to git:

```bash
PYTHONPATH=src uv run python scripts/eval.py prepare --samples-per-source 2
```

This downloads from:

- [Sparrow Invoice Dataset](https://huggingface.co/datasets/katanaml-org/invoices-donut-data-v1)
  (MIT, public/ungated). Attribution: Katana ML; original source is Kozłowski and
  Weichbroth, Mendeley Data, DOI `10.17632/tnj49gpmtz.2`. Supported fields are
  mapped from the dataset's `gt_parse` annotation; currency is unavailable and
  remains null.
- [InvoicesReceiptsPT](https://huggingface.co/datasets/Francisco-Cruz/InvoicesReceiptsPT)
  (Apache-2.0, public/ungated). Its image and JSON annotation files are paired
  by filename. The available annotation fields map to invoice number, date,
  supplier, tax, and total; buyer name, subtotal, and currency remain null.

The preparer checks the current Hugging Face license metadata before download,
records the repository revision, source/sample ID, attribution, label mapping,
excluded fields, and case type in `manifest.json`, and uses a seeded stable
sample selection. Example larger run:

```bash
PYTHONPATH=src uv run python scripts/eval.py prepare \
  --sample-count sparrow=50 --sample-count invoicesreceiptspt=20 \
  --seed 17 --output eval/local/large
```

Downloaded images and annotations are cached under the selected output directory
and reused on later preparations at the same source revision.

Generated fixtures include the original image, single- and multi-page PDFs,
multi-page TIFF, CSV, multi-sheet XLSX with a preamble above the header,
matched/mismatched PDF-spreadsheet pair labels, a planted total mismatch,
duplicate, corrupt/empty/password-protected PDFs, and a wrong-extension upload.
XLS generation is explicitly reported as unsupported because this project has
no XLS writer dependency. The optional `--stress-pages 1000` creates a separately
invoked stress PDF; stress fixtures are excluded from normal runs.

The runner uploads each fixture to the running application's HTTP API, polls
each job with bounded timeouts, retrieves final document results, and writes
`results.json` plus `report.md` beside the manifest:

```bash
PYTHONPATH=src uv run python scripts/eval.py run \
  --manifest eval/local/manifest.json --api-url http://localhost:8000
```

Run stress separately with `--stress`. Configure `--timeout` and
`--poll-interval` for slower environments. Exact-match field accuracy only
uses non-null labeled fields from labeled source examples; unlabeled realism
and generated-format cases are reported separately. Processing rates are
reported by source and format, and planted validation outcomes and latency are
reported separately. Timeouts and unexpected failures produce a non-zero exit
code and are retained in the machine-readable results.

The High Quality Invoice Images for OCR source is not enabled: Hugging Face
metadata reports ODbL, while its card points to an original Kaggle license that
must be checked independently. CORD, SROIE, and RVL-CDIP are also not enabled
because their access and license requirements were not verified for this
workflow. Do not treat generated format conversions as independent real-world
examples or use their ground truth to claim benchmark-quality performance.

Offline evaluation unit tests (no dataset download or running app):

```bash
uv run --group dev pytest -q tests/test_eval.py
```

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
