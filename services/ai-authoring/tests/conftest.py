import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ai-authoring-0123")
os.environ.setdefault("POSTGRES_DB", "x")
os.environ.setdefault("POSTGRES_USER", "x")
os.environ.setdefault("POSTGRES_PASSWORD", "x")
os.environ.setdefault("OPENAI_API_KEY", "x")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from collections.abc import AsyncIterator  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

import httpx  # noqa: E402
import jwt  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from authoring import models  # noqa: E402,F401
from authoring.db import Base, get_db  # noqa: E402
from authoring.models import AuthoringSession, Run  # noqa: E402
from authoring.pipeline import plan_apply  # noqa: E402
from authoring.pipeline.context import RunContext  # noqa: E402
from authoring.polygon.client import PolygonClient  # noqa: E402
from authoring.settings import settings  # noqa: E402
from tests.fakes import FakeBackend, FakeLLM  # noqa: E402

USER_ID = 7


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(settings, "BUILD_POLL_SECONDS", 0)
    monkeypatch.setattr(plan_apply, "TESTS_WAIT_SECONDS", 0)


@pytest.fixture
async def db_factory() -> AsyncIterator[async_sessionmaker]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool,
                                 connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def db(db_factory):
    async with db_factory() as session:
        yield session


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def client_factory(backend):
    def make(user_id: int) -> PolygonClient:
        return PolygonClient(user_id, transport=backend.transport(), base_url="http://backend/api")
    return make


@pytest.fixture
def problem(backend):
    return backend.add_problem("a-plus-b")


@pytest.fixture
async def session_row(db, problem) -> AuthoringSession:
    row = AuthoringSession(user_id=USER_ID, polygon_id=problem.id, model="anthropic/claude-opus-5.5",
                           settings={"auto_build": True})
    db.add(row)
    await db.commit()
    return row


@pytest.fixture
def make_ctx(db, session_row, client_factory, llm):
    async def make(kind: str = "chat", payload: dict | None = None) -> RunContext:
        run = Run(session_id=session_row.id, user_id=USER_ID, kind=kind, payload=payload or {}, status="running")
        db.add(run)
        await db.commit()
        return RunContext(db=db, run=run, session=session_row, client=client_factory(USER_ID), llm=llm)
    return make


def token(user_id: int = USER_ID, *, minutes: int = 10) -> str:
    now = datetime.now(UTC)
    return jwt.encode({"user_id": user_id, "exp": int((now + timedelta(minutes=minutes)).timestamp())},
                      settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.fixture
async def api(db_factory, llm, client_factory):
    from authoring.api import routes
    from authoring.main import app

    async def override_db():
        async with db_factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[routes.get_llm] = lambda: llm
    app.dependency_overrides[routes.get_client_factory] = lambda: client_factory
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ai",
                                 headers={"Authorization": f"Bearer {token()}"}) as client:
        yield client
    app.dependency_overrides.clear()
