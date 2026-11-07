from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.documents import router as documents_router
from .api.health import router as health_router
from .api.search import router as search_router
from .api.uploads import router as uploads_router
from .config import settings

app = FastAPI(title="DocIntel API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(uploads_router)
app.include_router(documents_router)
app.include_router(search_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok"}
