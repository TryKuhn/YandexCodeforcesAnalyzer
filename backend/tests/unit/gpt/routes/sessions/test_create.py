"""Unit tests for routes.sessions.create.create_session (direct handler call)."""
import pytest
from sqlalchemy import select

from api.pydantic_schemas.user.ai_task import AIStatementResponse, AIStatementRequest
from api.user.gpt.routes.sessions import create as create_mod
from api.user.gpt.routes.sessions.create import create_session
from models.task.session import PipelineStage, ProblemType, TaskSession

MOD = "api.user.gpt.routes.sessions.create"


@pytest.mark.asyncio
async def test_create_without_idea_returns_dict(db, user, monkeypatch):
    called = {"gen": False}

    async def fake_generate(**kwargs):
        called["gen"] = True
        return {"name": "X"}

    monkeypatch.setattr(create_mod.statement_gen, "generate", fake_generate)

    req = AIStatementRequest(idea="", model="anthropic/claude-opus-4.8")
    res = await create_session(req, user_id=user.id, db=db)

    assert called["gen"] is False
    assert res["statement"] is None
    assert res["stage"] == PipelineStage.STATEMENT
    rows = (await db.execute(select(TaskSession))).scalars().all()
    assert len(rows) == 1
    assert rows[0].problem_type == ProblemType.REGULAR


@pytest.mark.asyncio
async def test_create_with_idea_generates_statement(db, user, monkeypatch):
    async def fake_generate(**kwargs):
        return {"name": "Sum", "legend": "L"}

    monkeypatch.setattr(create_mod.statement_gen, "generate", fake_generate)

    req = AIStatementRequest(idea="add two numbers", model="anthropic/claude-opus-4.8")
    res = await create_session(req, user_id=user.id, db=db)

    assert isinstance(res, AIStatementResponse)
    assert res.statement == {"name": "Sum", "legend": "L"}
    saved = (await db.execute(select(TaskSession))).scalars().one()
    assert saved.statement == {"name": "Sum", "legend": "L"}


@pytest.mark.asyncio
async def test_create_generation_failure_raises_500(db, user, monkeypatch):
    async def boom(**kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(create_mod.statement_gen, "generate", boom)

    req = AIStatementRequest(idea="x", model="anthropic/claude-opus-4.8")
    with pytest.raises(Exception) as exc:
        await create_session(req, user_id=user.id, db=db)
    assert getattr(exc.value, "status_code", None) == 500
