import asyncio
import uuid
from pathlib import Path

import pytest
from fpdf import FPDF

from docintel import worker
from docintel.config import settings
from docintel.models import (
    Document,
    DocumentText,
    Extraction,
    Job,
)


class FakeSession:
    def __init__(self, store: list) -> None:
        self._store = store

    def add(self, instance) -> None:
        self._store.append(instance)

    async def get(self, model, entity_id):
        for obj in self._store:
            if isinstance(obj, model) and getattr(obj, "id", None) == entity_id:
                return obj
        return None

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def execute(self, stmt):
        model = None
        try:
            model = stmt.column_descriptions[0]["type"]
        except Exception:  # noqa: BLE001
            try:
                model = stmt.column_descriptions[0]["entity"]
            except Exception:  # noqa: BLE001
                model = None

        class Result:
            def __init__(self, items):
                self._items = items

            def scalars(self):
                return self

            def all(self):
                return list(self._items)

        if model is None:
            return Result([])
        items = [o for o in self._store if isinstance(o, model)]
        return Result(items)


@pytest.fixture
def fake_factory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    store: list = []

    class _AsyncCtx:
        async def __aenter__(self):
            return FakeSession(store)

        async def __aexit__(self, *exc):
            return False

    def factory():
        return _AsyncCtx()

    monkeypatch.setattr(worker, "async_session_factory", factory)
    monkeypatch.setattr(settings, "extractor", "fake")
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    # expose store via attribute for tests
    factory.store = store  # type: ignore[attr-defined]
    return store


def _make_pdf(path: Path, text: str = "Invoice INV-1 Total 110.00") -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, text)
    pdf.output(str(path))
    return path


def test_worker_processes_document(fake_factory) -> None:
    store = fake_factory
    tmp = Path(settings.data_dir)
    pdf_path = _make_pdf(tmp / "inv.pdf")

    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    async def seed():
        async with worker.async_session_factory() as s:
            doc = Document(
                id=doc_id,
                filename="inv.pdf",
                content_type="application/pdf",
                size=10,
                storage_path=str(pdf_path),
                status="queued",
            )
            job = Job(id=job_id, document_id=doc_id, kind="process_document", status="queued")
            s.add(doc)
            s.add(job)
            await s.commit()

    asyncio.run(seed())

    asyncio.run(worker.process_document({}, str(job_id), str(doc_id)))

    doc = _find_sync(store, Document, doc_id)
    job = _find_sync(store, Job, job_id)
    assert doc is not None and job is not None
    assert doc.status in {"done", "needs_review"}
    assert job.status == "complete"
    texts = [o for o in store if isinstance(o, DocumentText)]
    assert texts and "INV-1" in (texts[-1].full_text or "")
    exts = [o for o in store if isinstance(o, Extraction)]
    assert exts
    assert exts[-1].data.get("invoice_number") == "INV-FAKE-001"


def _find_sync(store, model, entity_id):
    for obj in store:
        if isinstance(obj, model) and getattr(obj, "id", None) == entity_id:
            return obj
    return None


def test_worker_failure_marks_failed(fake_factory, tmp_path: Path) -> None:
    store = fake_factory
    pdf_path = tmp_path / "missing.txt"
    # unsupported extension -> processing should fail

    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    async def seed():
        async with worker.async_session_factory() as s:
            doc = Document(
                id=doc_id,
                filename="bad.pdf",
                content_type="application/pdf",
                size=5,
                storage_path=str(pdf_path),
                status="queued",
            )
            job = Job(id=job_id, document_id=doc_id, kind="process_document", status="queued")
            s.add(doc)
            s.add(job)
            await s.commit()

    asyncio.run(seed())

    asyncio.run(worker.process_document({}, str(job_id), str(doc_id)))

    doc = _find_sync(store, Document, doc_id)
    job = _find_sync(store, Job, job_id)
    assert doc.status == "failed"
    assert job.status == "failed"
