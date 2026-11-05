from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from docintel import storage
from docintel.db import get_db
from docintel.main import app
from docintel.models import Document, Job


class FakeDatabase:
    def __init__(self) -> None:
        self.objects: list[Document | Job] = []

    def add(self, instance: Document | Job) -> None:
        self.objects.append(instance)

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        self.objects.clear()

    async def get(self, model: type[Job], job_id: uuid.UUID) -> Job | None:
        return next(
            (
                instance
                for instance in self.objects
                if isinstance(instance, model) and instance.id == job_id
            ),
            None,
        )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    database = FakeDatabase()

    async def override_get_db() -> AsyncGenerator[FakeDatabase, None]:
        yield database

    async def enqueue_job(job_id: str, document_id: str) -> None:
        pass

    monkeypatch.setattr(storage.settings, "data_dir", str(tmp_path))
    from docintel.api import uploads

    monkeypatch.setattr(uploads, "enqueue_processing_job", enqueue_job)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_upload_creates_document_and_queued_job(client: TestClient) -> None:
    response = client.post(
        "/api/documents/upload",
        files=[("files", ("invoices.csv", b"invoice,total\nINV-1,25.00\n", "text/csv"))],
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["document_ids"]) == 1
    assert len(body["job_ids"]) == 1
    job_response = client.get(f"/api/jobs/{body['job_ids'][0]}")
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "queued"


def test_corrupt_upload_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/documents/upload",
        files=[("files", ("broken.pdf", b"not a pdf", "application/pdf"))],
    )

    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_unknown_job_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/jobs/{uuid.uuid4()}")
    assert response.status_code == 404
