from sqlalchemy.dialects.postgresql import JSONB

from docintel.db import Base
from docintel.models import (
    Document,
    DocumentText,
    Embedding,
    Extraction,
    Job,
    ProcessingHistory,
    ValidationError,
)


def test_schema_has_required_tables_and_columns() -> None:
    assert set(Base.metadata.tables) == {
        "documents",
        "document_text",
        "extractions",
        "validation_errors",
        "jobs",
        "processing_history",
        "embeddings",
    }

    expected_columns = {
        Document: {"id", "filename", "content_type", "size", "storage_path", "status", "created_at", "updated_at"},
        DocumentText: {"document_id", "full_text", "page_count"},
        Extraction: {"document_id", "data", "model", "created_at"},
        ValidationError: {"document_id", "code", "message", "field", "created_at"},
        Job: {"id", "document_id", "kind", "status", "error", "created_at", "finished_at"},
        ProcessingHistory: {"id", "document_id", "event", "detail", "created_at"},
        Embedding: {"document_id", "vector"},
    }
    for model, columns in expected_columns.items():
        assert columns <= set(model.__table__.columns.keys())


def test_extraction_data_and_embedding_types() -> None:
    assert isinstance(Extraction.__table__.c.data.type, JSONB)
    assert Embedding.__table__.c.vector.type.dim == 384
