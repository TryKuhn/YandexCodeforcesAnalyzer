"""Async SQLAlchemy engine, session factory and the declarative base."""
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from authoring.settings import settings

# every table of this service carries the prefix, so the backend's alembic can
# skip them (and ours skips the backend's)
TABLE_PREFIX = "authoring_"


class Base(DeclarativeBase):
    """Declarative base of the service's models."""


def utcnow() -> datetime:
    """Naive UTC, like the backend."""
    return datetime.now(UTC).replace(tzinfo=None)


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request."""
    async with Session() as db:
        yield db
