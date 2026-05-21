"""
Shared test client backed by an in-memory SQLite database.

Sets up a single aiosqlite engine (StaticPool, shared connection), overrides
the FastAPI `get_db` dependency, and also patches the module-level `Session`
factories used directly by middlewares and background tasks.
"""

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.pool import StaticPool

# ── Test engine (SQLite in-memory, single shared connection) ─────────────────
_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_test_engine = create_async_engine(
    _TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = async_sessionmaker(
    bind=_test_engine, class_=AsyncSession, expire_on_commit=False
)


async def _bootstrap():
    from models.base import Base
    from models.user.role import Role

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _TestSession() as session:
        result = await session.execute(select(Role).filter_by(name="User"))
        if not result.scalars().first():
            session.add(Role(name="User"))
            session.add(Role(name="Admin"))
            await session.commit()


asyncio.run(_bootstrap())


# ── Override get_db so FastAPI handlers use the test engine ──────────────────
async def _override_get_db():
    async with _TestSession() as session:
        yield session


from app.database import get_db  # noqa: E402
from app.server import app  # noqa: E402

app.dependency_overrides[get_db] = _override_get_db

import app.database as _db_module  # noqa: E402
# ── Patch module-level Session factories used directly by middlewares ─────────
# The update_last_seen_middleware in server.py uses `Session()` directly (not
# via get_db), so we must patch it to avoid connection attempts to PostgreSQL.
import app.server as _server_module  # noqa: E402

_server_module.Session = _TestSession
_db_module.Session = _TestSession

client = TestClient(app)
