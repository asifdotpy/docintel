# AI Development Disclosure

## Models used

- Extraction LLM: Gemini 2.0 Flash (via OpenAI-compatible endpoint) in production; deterministic fake mode for tests/offline.
- Coding assistant: used throughout to scaffold FastAPI/arq/Next.js, write tests, and draft docs. All generated code was reviewed and edited by the candidate.

## Prompts

The extraction prompt is defined in `src/docintel/extract/schema.py` (`EXTRACTION_PROMPT`). It instructs the model to return JSON matching the invoice schema, use null for missing/unclear fields, and never invent values. The response is constrained with `response_format: json_schema` (strict) and temperature 0.

## What was generated vs. hand-written

- Generated then reviewed: boilerplate (FastAPI app, SQLAlchemy models, arq worker skeleton, Next.js components, test scaffolding).
- Hand-written / decided by candidate: stack lock-in (`docs/DECISIONS.md`), validation rules and duplicate detection logic, task decomposition and tracker, evaluation harness design, manual correction + re-validation flow.

## Data handling

- No real customer data was used; evaluation uses synthetic invoices.
- Secrets (GEMINI_API_KEY) are read from `.env` and never committed (`.gitignore`).
- AI-generated content is not presented as human-authored without review.
