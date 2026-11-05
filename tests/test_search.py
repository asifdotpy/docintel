import uuid

import pytest
from fastapi.testclient import TestClient

from docintel.db import get_db
from docintel.main import app
from docintel.models import Document, Extraction


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

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed(session: FakeSession):
    d1 = Document(id=uuid.uuid4(), filename="a.pdf", content_type="application/pdf", size=1, storage_path="/tmp/a", status="done")
    d2 = Document(id=uuid.uuid4(), filename="b.pdf", content_type="application/pdf", size=1, storage_path="/tmp/b", status="queued")
    e1 = Extraction(document_id=d1.id, data={"supplier_name": "Acme", "customer_name": "Beta", "invoice_number": "INV-1"}, model="fake")
    e2 = Extraction(document_id=d2.id, data={"supplier_name": "Globex", "customer_name": "Beta", "invoice_number": "INV-2"}, model="fake")
    session.add(d1)
    session.add(d2)
    session.add(e1)
    session.add(e2)
    return d1, d2


def test_keyword_filter_supplier(client: TestClient) -> None:
    # need seeded session; re-seed via a new session override
    session = FakeSession()
    _d1, _d2 = _seed(session)

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    resp = client.get("/api/search?supplier=Acme")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["extraction"]["supplier_name"] == "Acme"


def test_keyword_filter_status(client: TestClient) -> None:
    session = FakeSession()
    _d1, _d2 = _seed(session)

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    resp = client.get("/api/search?status=queued")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "queued"


def test_keyword_filter_invoice_number(client: TestClient) -> None:
    session = FakeSession()
    _d1, _d2 = _seed(session)

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    resp = client.get("/api/search?invoice_number=INV-2")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1


def test_invalid_mode_returns_400(client: TestClient) -> None:
    resp = client.get("/api/search?mode=nope")
    assert resp.status_code == 400


def test_semantic_mode_no_crash(client: TestClient) -> None:
    session = FakeSession()
    _seed(session)

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    resp = client.get("/api/search?mode=semantic&q=invoice")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
