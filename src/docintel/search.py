from __future__ import annotations

import math
from typing import Any

try:
    from fastembed import TextEmbedding

    _FASTEMBED_AVAILABLE = True
except Exception:  # noqa: BLE001
    _FASTEMBED_AVAILABLE = False

from .config import settings
from .models import Document, Embedding, Extraction


async def _all_of_async(db: Any, model: type) -> list:
    if hasattr(db, "execute"):
        result = await db.execute(__import__("sqlalchemy").select(model))
        return list(result.scalars().all())
    return [obj for obj in getattr(db, "objects", []) if isinstance(obj, model)]


def _extraction_for(document_id, extractions: list) -> dict | None:
    matches = [e for e in extractions if e.document_id == document_id]
    if not matches:
        return None
    matches.sort(key=lambda e: getattr(e, "created_at", None) or 0)
    return matches[-1].data if matches[-1].data is not None else None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    # Cast explicitly: embedding vectors may be numpy float32, which Pydantic
    # cannot serialize when returned in an API response.
    return float(dot / (na * nb))


def _embed(text: str) -> list[float] | None:
    if not _FASTEMBED_AVAILABLE:
        return None
    try:
        model = TextEmbedding(model_name=settings.embedding_model)
        vectors = list(model.embed([text]))
        return list(vectors[0]) if vectors else None
    except Exception:  # noqa: BLE001
        return None


async def keyword_search(
    db: Any,
    status: str | None = None,
    supplier: str | None = None,
    customer: str | None = None,
    invoice_number: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    documents = await _all_of_async(db, Document)
    extractions = await _all_of_async(db, Extraction)

    results: list[dict[str, Any]] = []
    for doc in documents:
        if status and doc.status != status:
            continue
        data = _extraction_for(doc.id, extractions) or {}
        if supplier and supplier.lower() not in str(data.get("supplier_name") or "").lower():
            continue
        if customer and customer.lower() not in str(data.get("customer_name") or "").lower():
            continue
        if invoice_number and invoice_number.lower() not in str(data.get("invoice_number") or "").lower():
            continue
        if q and q.lower() not in (doc.filename or "").lower() and q.lower() not in str(data).lower():
            continue
        # date range: best-effort on invoice_date string
        inv_date = data.get("invoice_date")
        if date_from and inv_date and str(inv_date) < date_from:
            continue
        if date_to and inv_date and str(inv_date) > date_to:
            continue
        results.append(
            {
                "id": str(doc.id),
                "filename": doc.filename,
                "status": doc.status,
                "extraction": data,
                "score": None,
            }
        )
    return results


async def semantic_search(
    db: Any,
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if not _FASTEMBED_AVAILABLE:
        return []
    query_vec = _embed(query)
    if query_vec is None:
        return []

    documents = await _all_of_async(db, Document)
    extractions = await _all_of_async(db, Extraction)
    embeddings = await _all_of_async(db, Embedding)

    doc_map = {d.id: d for d in documents}
    scored: list[tuple[float, Any]] = []
    for emb in embeddings:
        score = _cosine(query_vec, list(emb.vector))
        doc = doc_map.get(emb.document_id)
        if doc is not None:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    results: list[dict[str, Any]] = []
    for score, doc in scored[:limit]:
        data = _extraction_for(doc.id, extractions) or {}
        results.append(
            {
                "id": str(doc.id),
                "filename": doc.filename,
                "status": doc.status,
                "extraction": data,
                "score": round(score, 4),
            }
        )
    return results


async def search(
    db: Any,
    q: str | None = None,
    mode: str = "keyword",
    status: str | None = None,
    supplier: str | None = None,
    customer: str | None = None,
    invoice_number: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if mode == "semantic" and q:
        return await semantic_search(db, q, limit=limit)
    if mode == "hybrid" and q:
        sem = await semantic_search(db, q, limit=limit)
        kw = await keyword_search(
            db,
            status=status,
            supplier=supplier,
            customer=customer,
            invoice_number=invoice_number,
            date_from=date_from,
            date_to=date_to,
            q=q,
        )
        # merge by id, prefer semantic score
        by_id: dict[str, dict[str, Any]] = {}
        for r in kw:
            by_id[r["id"]] = r
        for r in sem:
            if r["id"] in by_id:
                by_id[r["id"]]["score"] = r["score"]
            else:
                by_id[r["id"]] = r
        return list(by_id.values())[:limit]
    return await keyword_search(
        db,
        status=status,
        supplier=supplier,
        customer=customer,
        invoice_number=invoice_number,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )
