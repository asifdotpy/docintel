from arq import create_pool
from arq.connections import RedisSettings

from .config import settings


async def enqueue_processing_job(job_id: str, document_id: str) -> None:
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await redis.enqueue_job(
            "process_document",
            job_id,
            document_id,
            _job_id=f"process:{job_id}",
        )
    finally:
        await redis.aclose()
