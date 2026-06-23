"""Unit tests for routes.statement.refine.refine_statement."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import RefineRequest
from api.user.gpt.routes.statement import refine as mod
from api.user.gpt.routes.statement.refine import refine_statement
from models.task.session import PipelineStage


@pytest.mark.asyncio
async def test_refine_statement_stage_no_files(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "Old"}
    await db.commit()

    async def fake_stmt_gen(**kwargs):
        return {"name": "New", "legend": "L"}

    called = {"pack": False}

    async def fake_pack(*a, **k):
        called["pack"] = True
        return {}

    monkeypatch.setattr(mod.statement_gen, "generate", fake_stmt_gen)
    monkeypatch.setattr(mod.file_gen, "generate_pack", fake_pack)

    req = RefineRequest(session_id=task_session.id, feedback="make it harder")
    res = await refine_statement(req, user_id=user.id, db=db)
    assert res["statement"]["name"] == "New"
    assert res["session_id"] == task_session.id
    # STATEMENT stage does not regenerate files
    assert called["pack"] is False
    assert "technical_data" not in res
    await db.refresh(task_session)
    # history accumulates prior assistant statement + user feedback
    assert any(m["role"] == "user" and m["content"] == "make it harder"
               for m in task_session.history)


@pytest.mark.asyncio
async def test_refine_files_review_regenerates_files(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "Old"}
    task_session.stage = PipelineStage.FILES_REVIEW
    await db.commit()

    async def fake_stmt_gen(**kwargs):
        return {"name": "New"}

    async def fake_pack(problem_type, stmt, model):
        return {"checker": "chk"}

    monkeypatch.setattr(mod.statement_gen, "generate", fake_stmt_gen)
    monkeypatch.setattr(mod.file_gen, "generate_pack", fake_pack)

    req = RefineRequest(session_id=task_session.id, feedback="x")
    res = await refine_statement(req, user_id=user.id, db=db)
    assert res["technical_data"] == {"checker": "chk"}


@pytest.mark.asyncio
async def test_refine_files_review_swallows_pack_error(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "Old"}
    task_session.stage = PipelineStage.FILES_REVIEW
    await db.commit()

    async def fake_stmt_gen(**kwargs):
        return {"name": "New"}

    async def boom(*a, **k):
        raise RuntimeError("pack failed")

    monkeypatch.setattr(mod.statement_gen, "generate", fake_stmt_gen)
    monkeypatch.setattr(mod.file_gen, "generate_pack", boom)

    req = RefineRequest(session_id=task_session.id, feedback="x")
    res = await refine_statement(req, user_id=user.id, db=db)
    # error swallowed: no technical_data key, statement still updated
    assert "technical_data" not in res
    assert res["statement"]["name"] == "New"


@pytest.mark.asyncio
async def test_refine_wrong_stage_400(db, user, task_session):
    task_session.stage = PipelineStage.DONE
    await db.commit()
    req = RefineRequest(session_id=task_session.id, feedback="x")
    with pytest.raises(HTTPException) as exc:
        await refine_statement(req, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_refine_404(db, user):
    req = RefineRequest(session_id="nope", feedback="x")
    with pytest.raises(HTTPException) as exc:
        await refine_statement(req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
