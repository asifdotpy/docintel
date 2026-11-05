from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import ClassVar

from arq.connections import RedisSettings
from sqlalchemy import select

from .config import settings
from .db import async_session_factory
from .extract import extract_invoice
from .models import (
    Document,
    DocumentText,
    Embedding,
    Extraction,
    Job,
    ProcessingHistory,
    ValidationError,
)
from .pipeline import pdf_text, spreadsheet
from .pipeline import router as parse_router
from .pipeline.ocr import image as ocr_image
from .pipeline.ocr import pdf as ocr_pdf
from .validate import validate

logger = logging.getLogger(__name__)

try:
    from fastembed import TextEmbedding

    _FASTEMBED_AVAILABLE = True
except Exception:  # noqa: BLE001
    _FASTEMBED_AVAILABLE = False


async def _record_history(session, document_id, event, detail=None):
    session.add(ProcessingHistory(document_id=document_id, event=event, detail=detail))


async def process_document(ctx, job_id: str, document_id: str) -> None:
    job_uuid = uuid.UUID(job_id)
    doc_uuid = uuid.UUID(document_id)

    async with async_session_factory() as session:
        job = await session.get(Job, job_uuid)
        document = await session.get(Document, doc_uuid)
        if job is None or document is None:
            logger.error("Missing job or document: %s %s", job_id, document_id)
            return

        job.status = "running"
        document.status = "processing"
        await _record_history(session, doc_uuid, "started", "Processing began.")
        await session.commit()

        try:
            path = document.storage_path

            # 1. Route + parse
            kind = parse_router.detect(path)
            text = ""
            page_count = None
            if kind == "pdf_text":
                result = pdf_text.extract(path)
                text = result["text"]
                page_count = result["page_count"]
            elif kind == "pdf_ocr":
                result = ocr_pdf(path)
                text = result["text"]
                page_count = result["page_count"]
            elif kind == "image":
                text = ocr_image(path)
                page_count = 1
            elif kind == "spreadsheet":
                result = spreadsheet.parse(path)
                text = result["text"]
            else:
                raise ValueError(f"Unknown parser kind: {kind}")

            # Store extracted text
            existing_text = await session.get(DocumentText, doc_uuid)
            if existing_text is None:
                session.add(DocumentText(document_id=doc_uuid, full_text=text, page_count=page_count))
            else:
                existing_text.full_text = text
                existing_text.page_count = page_count

            # Remove stale validation errors / extraction for this document.
            existing_errors = await session.execute(
                select(ValidationError).where(ValidationError.document_id == doc_uuid)
            )
            for e in existing_errors.scalars().all():
                await session.delete(e)
            # (keep prior extractions as history; latest is selected by created_at)

            await _record_history(session, doc_uuid, "parsed", f"kind={kind}")

            # 2. Extract invoice (best-effort; empty text yields nulls)
            invoice = extract_invoice(text) if text.strip() else None

            # 3. Validate
            existing_keys: set[tuple] = set()
            ext_result = await session.execute(select(Extraction))
            for ext in ext_result.scalars().all():
                if ext.document_id == doc_uuid:
                    continue
                data = ext.data or {}
                key = (data.get("invoice_number"), data.get("supplier_name"))
                if key != (None, None):
                    existing_keys.add(key)

            issues: list[dict] = []
            if invoice is not None:
                issues = validate(invoice, existing_keys=existing_keys)
                session.add(
                    Extraction(
                        document_id=doc_uuid,
                        data=invoice.model_dump(),
                        model=settings.extractor or "fake",
                    )
                )
                for issue in issues:
                    session.add(
                        ValidationError(
                            document_id=doc_uuid,
                            code=issue["code"],
                            field=issue["field"],
                            message=issue["message"],
                        )
                    )

            await _record_history(session, doc_uuid, "extracted", f"issues={len(issues)}")

            # 4. Embed (optional)
            if text.strip() and _FASTEMBED_AVAILABLE:
                try:
                    model = TextEmbedding(model_name=settings.embedding_model)
                    vectors = list(model.embed([text]))
                    if vectors:
                        vec = list(vectors[0])
                        existing_emb = await session.get(Embedding, doc_uuid)
                        if existing_emb is None:
                            session.add(Embedding(document_id=doc_uuid, vector=vec))
                        else:
                            existing_emb.vector = vec
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Embedding failed: %s", exc)

            # 5. Final status
            if invoice is None:
                document.status = "needs_review"
            else:
                document.status = "done" if not issues else "needs_review"
            job.status = "complete"
            job.finished_at = datetime.now(UTC)
            await _record_history(session, doc_uuid, "completed", "Processing finished.")
            await session.commit()

        except Exception as exc:
            logger.exception("Processing failed for %s", document_id)
            try:
                job.status = "failed"
                job.error = str(exc)
                document.status = "failed"
                await _record_history(session, doc_uuid, "failed", str(exc))
                await session.commit()
            except Exception:  # noqa: BLE001
                await session.rollback()
            # Do not re-raise: failure is recorded; arq retry is optional.


class WorkerSettings:
    functions: ClassVar = [process_document]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 300
    keep_result = 300
