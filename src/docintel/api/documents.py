from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..extract.schema import Invoice
from ..models import Document, Extraction, Job, ValidationError
from ..queue import enqueue_processing_job
from ..validate import validate

router = APIRouter()


class CorrectionRequest(BaseModel):
    fields: dict[str, Any]


async def _all_of(db: AsyncSession | Any, model: type) -> list:
    if hasattr(db, "execute"):
        result = await db.execute(select(model))
        return list(result.scalars().all())
    return [obj for obj in getattr(db, "objects", []) if isinstance(obj, model)]


async def _get_document(db: Any, document_id: uuid.UUID) -> Document | None:
    if hasattr(db, "get"):
        return await db.get(Document, document_id)
    for obj in getattr(db, "objects", []):
        if isinstance(obj, Document) and obj.id == document_id:
            return obj
    return None


@router.get("/api/documents")
async def list_documents(
    db: Annotated[Any, Depends(get_db)],
    status: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    documents = await _all_of(db, Document)
    if status:
        documents = [d for d in documents if d.status == status]
    if q:
        documents = [d for d in documents if q.lower() in (d.filename or "").lower()]
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "status": d.status,
            "created_at": d.created_at.isoformat() if getattr(d, "created_at", None) else None,
        }
        for d in documents
    ]


@router.get("/api/documents/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    db: Annotated[Any, Depends(get_db)],
) -> dict[str, Any]:
    document = await _get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    extractions = [e for e in await _all_of(db, Extraction) if e.document_id == document_id]
    indexed = list(enumerate(extractions))
    indexed.sort(key=lambda item: (getattr(item[1], "created_at", None) or 0, item[0]), reverse=True)
    latest = indexed[0][1] if indexed else None

    errors = [e for e in await _all_of(db, ValidationError) if e.document_id == document_id]

    return {
        "document": {
            "id": str(document.id),
            "filename": document.filename,
            "content_type": document.content_type,
            "size": document.size,
            "storage_path": document.storage_path,
            "status": document.status,
        },
        "extraction": latest.data if latest is not None else None,
        "validation_errors": [
            {"id": e.id, "code": e.code, "field": e.field, "message": e.message}
            for e in errors
        ],
    }


@router.patch("/api/documents/{document_id}")
async def correct_document(
    document_id: uuid.UUID,
    payload: CorrectionRequest,
    db: Annotated[Any, Depends(get_db)],
) -> dict[str, Any]:
    document = await _get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    extractions = [e for e in await _all_of(db, Extraction) if e.document_id == document_id]
    indexed = list(enumerate(extractions))
    indexed.sort(key=lambda item: (getattr(item[1], "created_at", None) or 0, item[0]), reverse=True)
    latest = indexed[0][1] if indexed else None
    data = dict(latest.data) if latest is not None else {}
    data.update(payload.fields)

    new_extraction = Extraction(
        document_id=document_id,
        data=data,
        model="manual",
    )
    db.add(new_extraction)

    # Re-run validation on the corrected data.
    existing_keys: set[tuple] = set()
    all_extractions = await _all_of(db, Extraction)
    for ext in all_extractions:
        if ext.document_id == document_id:
            continue
        ext_data = ext.data or {}
        existing_keys.add((ext_data.get("invoice_number"), ext_data.get("supplier_name")))
    # Exclude null/null keys to avoid false positives.
    existing_keys = {k for k in existing_keys if k != (None, None)}

    try:
        invoice = Invoice.model_validate(data)
        issues = validate(invoice, existing_keys=existing_keys)
    except Exception:  # noqa: BLE001
        issues = []

    # Replace prior validation errors for this document.
    prior_errors = [e for e in await _all_of(db, ValidationError) if e.document_id == document_id]
    for e in prior_errors:
        try:
            getattr(db, "objects", []).remove(e)
        except ValueError:
            pass
        if hasattr(db, "delete"):
            await db.delete(e)
    for issue in issues:
        db.add(
            ValidationError(
                document_id=document_id,
                code=issue["code"],
                field=issue["field"],
                message=issue["message"],
            )
        )

    document.status = "done" if not issues else "needs_review"
    await db.commit()

    return {
        "document_id": str(document_id),
        "extraction": data,
        "validation_errors": [
            {"code": i["code"], "field": i["field"], "message": i["message"]} for i in issues
        ],
    }


@router.post("/api/documents/{document_id}/reprocess")
async def reprocess_document(
    document_id: uuid.UUID,
    db: Annotated[Any, Depends(get_db)],
) -> dict[str, str]:
    document = await _get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    job = Job(document_id=document_id, kind="process_document", status="queued")
    db.add(job)
    await db.commit()

    try:
        await enqueue_processing_job(str(job.id), str(document_id))
    except Exception:  # noqa: BLE001
        job.status = "failed"
        job.error = "Unable to enqueue processing job."
        document.status = "failed"
        await db.commit()
        raise HTTPException(status_code=503, detail="Unable to enqueue processing job.")

    document.status = "queued"
    await db.commit()
    return {"job_id": str(job.id)}
