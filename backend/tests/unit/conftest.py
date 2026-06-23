"""Shared fixtures for backend unit tests.

Provides a function-scoped in-memory SQLite session (every model table is
registered by importing ``app.server``) plus factories for the AI task entities
the service layer operates on, and a helper to stub the shared LLM client.
"""
from collections.abc import AsyncGenerator
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.pool import StaticPool

import app.server  # noqa: F401  — registers every model on Base.metadata


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a clean in-memory SQLite session with all tables created."""
    from models.base import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def user(db) -> "object":
    """Create and return a persisted User with Polygon credentials set."""
    from models.user.role import Role
    from models.user.user import User

    role = Role(name="User")
    db.add(role)
    await db.flush()
    u = User(
        login="tester",
        password="x",
        email="tester@example.com",
        role_id=role.id,
        polygon_api_key="key",
        polygon_api_secret="secret",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def task_session(db, user):
    """Create and return a persisted REGULAR TaskSession owned by ``user``."""
    from models.task.session import (PipelineStage, ProblemType, TaskSession)

    now = datetime(2026, 1, 1)
    s = TaskSession(
        id="sess-1",
        user_id=user.id,
        model="anthropic/claude-opus-4.8",
        system_prompt="",
        history=[],
        problem_type=ProblemType.REGULAR,
        stage=PipelineStage.STATEMENT,
        progress={"status": "idle"},
        statement=None,
        problem_settings={},
        polygon_problem_id=555,
        created_at=now,
        updated_at=now,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


@pytest.fixture
def stub_llm(monkeypatch):
    """Return a function that stubs ``llm.ask``/``llm.ask_text`` with fixed values.

    Usage: ``stub_llm(ask={"intent": "answer"}, ask_text="code")``.
    """
    from api.user.gpt.services.llm.client import llm

    def _apply(ask=None, ask_text=""):
        async def fake_ask(model, messages, json_mode=True):
            return ask if ask is not None else {}

        async def fake_ask_text(model, messages):
            return ask_text

        monkeypatch.setattr(llm, "ask", fake_ask)
        monkeypatch.setattr(llm, "ask_text", fake_ask_text)
        return llm

    return _apply
