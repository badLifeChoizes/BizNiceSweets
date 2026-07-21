"""
Async SQLAlchemy engine and session factory.

get_db() is the FastAPI dependency that yields an AsyncSession.
Alembic migrations use a separate sync engine (see alembic/env.py).
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency: yields a database session, closes on exit."""
    async with AsyncSessionLocal() as session:
        yield session
