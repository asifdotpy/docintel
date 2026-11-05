from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Document, Job
from ..queue import enqueue_processing_job
from ..storage import InvalidUploadError, StoredUpload, remove_stored_upload, store_upload

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/documents/upload")
async def upload_documents(
    files: Annotated[list[UploadFile], File()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, list[str]]:
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    stored_uploads: list[StoredUpload] = []
    documents: list[Document] = []
    jobs: list[Job] = []
    try:
        for upload in files:
            stored = await store_upload(upload)
            stored_uploads.append(stored)
            document_id = uuid.uuid4()
            job_id = uuid.uuid4()
            document = Document(
                id=document_id,
                filename=stored.filename,
                content_type=stored.content_type,
                size=stored.size,
                storage_path=str(stored.path),
                status="queued",
            )
            job = Job(
                id=job_id,
                document_id=document_id,
                kind="process_document",
                status="queued",
            )
            db.add(document)
            db.add(job)
            documents.append(document)
            jobs.append(job)

        await db.commit()
    except InvalidUploadError as error:
        await db.rollback()
        for stored in stored_uploads:
            remove_stored_upload(stored)
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception:
        await db.rollback()
        for stored in stored_uploads:
            remove_stored_upload(stored)
        raise
    finally:
        for upload in files:
            await upload.close()

    enqueue_errors: list[str] = []
    for job in jobs:
        try:
            await enqueue_processing_job(str(job.id), str(job.document_id))
        except (OSError, RedisError):
            logger.exception("Could not enqueue processing job %s", job.id)
            job.status = "failed"
            job.error = "Unable to enqueue processing job."
            document = next(doc for doc in documents if doc.id == job.document_id)
            document.status = "failed"
            enqueue_errors.append(str(job.id))

    if enqueue_errors:
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "One or more processing jobs could not be enqueued.",
                "job_ids": enqueue_errors,
            },
        )

    return {
        "document_ids": [str(document.id) for document in documents],
        "job_ids": [str(job.id) for job in jobs],
    }


@router.get("/api/jobs/{job_id}")
async def get_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str | None]:
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "id": str(job.id),
        "status": job.status,
        "error": job.error,
    }
