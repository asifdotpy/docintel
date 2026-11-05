# Architecture

```
           +-----------+          +-----------+
  Browser  | Next.js   |  HTTP    | FastAPI   |
  (React)  | apps/web  | -------> | src/      |
           +-----------+          +-----+-----+
                                       |
                  +--------------------+--------------------+
                  |                    |                    |
            +-----v-----+      +-------v-------+    +-------v-------+
            | Postgres  |      | Redis (arq)  |    | File storage  |
            | +pgvector |      | queue        |    | (data_dir)    |
            +-----------+      +-------+-------+    +---------------+
                                       |
                                 +-----v-----+
                                 | arq worker|
                                 | process_  |
                                 | document  |
                                 +-----+-----+
                                       |
        +------------------------------+------------------------------+
        |              |               |              |                 |
   pdf_text        ocr (tesseract)  spreadsheet    extract (LLM)   validate
   (digital)       (scanned/img)    (xlsx/csv)     (Gemini/fake)   (rules)
```

## Data flow

1. Upload (`POST /api/documents/upload`) saves files, creates Document + Job rows, enqueues arq jobs.
2. Worker (`process_document`) runs: detect kind -> parse -> store DocumentText -> extract Invoice -> validate -> store Extraction + ValidationError -> embed (fastembed) -> store Embedding -> update statuses.
3. Search (`GET /api/search`): keyword (ILIKE on text/fields), semantic (cosine on embeddings), hybrid (union).
4. Manual correction (`PATCH /api/documents/{id}`) updates Extraction and re-runs validation.
5. Reprocess (`POST /api/documents/{id}/reprocess`) re-enqueues a failed/old job.

## Database

Tables: documents, document_texts, extractions, validation_errors, embeddings, jobs, processing_history. Schema + migration in `src/docintel/models.py` and `alembic/`.
