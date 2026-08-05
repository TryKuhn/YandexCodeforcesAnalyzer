"""Fixtures for job-queue tests: a session factory (the worker opens its own sessions)."""
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.pool import StaticPool

import app.server  # noqa: F401  — registers every model on Base.metadata


@pytest_asyncio.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    from models.base import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


class FakeTransport:
    """In-memory stand-in for Redis Streams."""

    def __init__(self) -> None:
        self.entries: list[tuple[str, str]] = []
        self.reclaimable: list[tuple[str, str]] = []
        self.acked: list[str] = []
        self.pushed: list[str] = []
        self._counter = 0

    async def push(self, job_id: str) -> None:
        self._counter += 1
        self.pushed.append(job_id)
        self.entries.append((f"e{self._counter}", job_id))

    async def pull(self, consumer: str, count: int = 8, block_ms: int = 5000):
        out, self.entries = self.entries[:count], self.entries[count:]
        return out

    async def ack(self, entry_id: str) -> None:
        self.acked.append(entry_id)

    async def reclaim(self, consumer: str, min_idle_ms: int = 60_000, count: int = 8):
        out, self.reclaimable = self.reclaimable[:count], self.reclaimable[count:]
        return out


@pytest.fixture
def transport() -> FakeTransport:
    return FakeTransport()
