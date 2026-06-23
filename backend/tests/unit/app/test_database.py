"""Unit tests for app/database.py — get_db dependency yields an AsyncSession."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.database as db_mod


@pytest.mark.asyncio
async def test_get_db_yields_async_session(monkeypatch):
    # Replace the module Session factory with one backed by in-memory SQLite so
    # we never touch PostgreSQL.
    from sqlalchemy.ext.asyncio import (async_sessionmaker,
                                        create_async_engine)
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db_mod, "Session", maker)

    gen = db_mod.get_db()
    session = await gen.__anext__()
    assert isinstance(session, AsyncSession)
    # Exhaust the generator to trigger the `async with` cleanup.
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()
    await engine.dispose()


def test_module_exposes_engine_and_session():
    assert db_mod.engine is not None
    assert db_mod.Session is not None
