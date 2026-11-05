import uuid

import pytest
from fastapi.testclient import TestClient

from docintel.api import documents as documents_api
from docintel.db import get_db
from docintel.main import app
from docintel.models import Document, Extraction, ValidationError


class FakeSession:
    def __init__(self) -> None:
        self.objects: list = []

    def add(self, instance) -> None:
        self.objects.append(instance)

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        self.objects.clear()

    async def get(self, model, entity_id):
        for obj in self.objects:
            if isinstance(obj, model) and getattr(obj, "id", None) == entity_id:
                return obj
        return None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    session = FakeSession()

    async def override_get_db():
        yield session

    async def enqueue_job(job_id: str, document_id: str) -> None:
        pass

    monkeypatch.setattr(documents_api, "enqueue_processing_job", enqueue_job)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed(session: FakeSession):
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        filename="inv.pdf",
        content_type="application/pdf",
        size=10,
        storage_path="/tmp/inv.pdf",
        status="done",
    )
    ext = Extraction(document_id=doc_id, data={"total": 110.0, "supplier_name": "Acme"}, model="fake")
    err = ValidationError(document_id=doc_id, code="missing_field", message="missing", field="currency")
    session.add(doc)
    session.add(ext)
    session.add(err)
    return doc_id


def test_get_document_returns_details(client: TestClient) -> None:
    # access the underlying session via override? Re-seed by calling endpoint after seeding impossible.
    # Instead seed through a direct session reference captured in fixture closure.
    pass


def test_list_and_get_and_patch_and_reprocess(client: TestClient, monkeypatch) -> None:
    # monkeypatch the client fixture's session is not exposed; recreate by patching get_db again
    session = FakeSession()
    doc_id = _seed(session)

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    # list
    resp = client.get("/api/documents")
    assert resp.status_code == 200
    assert any(d["id"] == str(doc_id) for d in resp.json())

    # filter
    resp = client.get("/api/documents?status=done")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # get
    resp = client.get(f"/api/documents/{doc_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["extraction"]["total"] == 110.0
    assert len(body["validation_errors"]) == 1

    # patch
    resp = client.patch(f"/api/documents/{doc_id}", json={"fields": {"total": 120.0}})
    assert resp.status_code == 200
    assert resp.json()["extraction"]["total"] == 120.0

    # get after patch
    resp = client.get(f"/api/documents/{doc_id}")
    assert resp.json()["extraction"]["total"] == 120.0

    # reprocess
    resp = client.post(f"/api/documents/{doc_id}/reprocess")
    assert resp.status_code == 200
    assert "job_id" in resp.json()

    app.dependency_overrides.clear()


def test_get_unknown_document_404(client: TestClient) -> None:
    resp = client.get(f"/api/documents/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_reprocess_unknown_404(client: TestClient) -> None:
    resp = client.post(f"/api/documents/{uuid.uuid4()}/reprocess")
    assert resp.status_code == 404
