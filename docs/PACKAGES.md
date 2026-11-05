# Packages

Use these. Do not replace them with a larger framework mid-build.

| Job | Package | Why this one |
| --- | --- | --- |
| HTTP API | FastAPI, Pydantic v2 | Typed JSON and OpenAPI without a second backend language |
| Database | SQLAlchemy 2, Alembic, psycopg, Postgres | One store for rows, JSON, full text, and vectors |
| Vectors | pgvector | Avoids running a separate vector database |
| Queue | arq, Redis | Async worker with retries. FastAPI background tasks do not meet the brief |
| Digital PDF | pypdf | Reads the text layer. No model download |
| OCR | pytesseract, pdf2image, Pillow | System Tesseract plus light image cleanup |
| Spreadsheets | pandas, openpyxl, xlrd | xlsx, xls, and csv |
| Extraction | openai SDK against Gemini OpenAI-compatible endpoint | Gemini free tier for testing; structured outputs |
| Semantic search | fastembed (`search` extra) | Local 384-d vectors. The default test run does not download the model |
| Tests | pytest, httpx, fpdf2 | API tests and synthetic PDFs |
| UI | Next.js, Tailwind, react-dropzone | The only new npm package allowed is react-dropzone |

Install Python deps with `uv`. The lockfile is `uv.lock`. System packages for OCR, installed in T05: `tesseract-ocr` and `poppler-utils`.

## Left out on purpose

- **Docling and Unstructured.** They hide the text-versus-OCR branch the brief asks to show, and they download large models.
- **NestJS plus a Python sidecar.** Two backends for one assessment.
- **MongoDB, Elasticsearch, Qdrant.** Postgres already covers documents, keyword search, and vectors.
- **A custom OCR engine or a custom xlsx parser.**

`fastembed` is optional so the first backend task can install without the ONNX wheel:

```bash
uv sync --group dev                 # T01 through T09
uv sync --group dev --extra search  # T10
```
