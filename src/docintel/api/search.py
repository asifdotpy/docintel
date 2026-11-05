from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db
from ..search import search

router = APIRouter()


@router.get("/api/search")
async def search_documents(
    db: Annotated[Any, Depends(get_db)],
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
    if mode not in {"keyword", "semantic", "hybrid"}:
        raise HTTPException(status_code=400, detail="Invalid mode.")
    return await search(
        db,
        q=q,
        mode=mode,
        status=status,
        supplier=supplier,
        customer=customer,
        invoice_number=invoice_number,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
