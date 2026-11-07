# AI Development Disclosure

## Models used

- Extraction LLM: `gemini-3.5-flash-lite` by default (configurable with `GEMINI_MODEL`), called through Google's OpenAI-compatible endpoint; deterministic fake mode for tests/offline.
- Coding assistant: used throughout to scaffold FastAPI/arq/Next.js, write tests, and draft docs. All generated code was reviewed and edited by the candidate.

## Prompts

The extraction prompt is defined in `src/docintel/extract/schema.py` (`EXTRACTION_PROMPT`). It instructs the model to return JSON matching the invoice schema, use null for missing/unclear fields, and never invent values. The response is constrained with `response_format: json_schema` (strict) and temperature 0.

## What was generated vs. hand-written

- Generated then reviewed: boilerplate (FastAPI app, SQLAlchemy models, arq worker skeleton, Next.js components, test scaffolding).
- Hand-written / decided by candidate: stack lock-in (`docs/DECISIONS.md`), validation rules and duplicate detection logic, task decomposition and tracker, evaluation harness design, manual correction + re-validation flow.

## Data handling

- No real customer data was used. Evaluation uses four public, source-labeled invoice images from the Hugging Face datasets listed in the README, plus generated format-conversion and failure fixtures. The small labeled sample is not a production benchmark.
- Secrets (GEMINI_API_KEY) are read from `.env` and never committed (`.gitignore`).
- AI-generated content is not presented as human-authored without review.
