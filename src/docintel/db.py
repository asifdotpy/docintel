from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


async_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
async_session_factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

sync_engine = create_engine(settings.database_url, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
