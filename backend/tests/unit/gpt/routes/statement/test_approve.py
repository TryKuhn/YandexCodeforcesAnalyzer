"""Unit tests for routes.statement.approve.approve_statement."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import ApproveStatementRequest
from api.user.gpt.routes.statement import approve as mod
from api.user.gpt.routes.statement.approve import approve_statement
from api.user.gpt.services.ai_file_helpers import get_all_file_contents
from models.task.session import PipelineStage, ProblemType


@pytest.mark.asyncio
async def test_approve_happy_path_regular(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "P", "legend": "L"}
    await db.commit()

    async def fake_pack(problem_type, stmt, model):
        return {"checker": "chk", "solution_cpp": "sol"}

    monkeypatch.setattr(mod.file_gen, "generate_pack", fake_pack)

    req = ApproveStatementRequest(session_id=task_session.id)
    res = await approve_statement(req, user_id=user.id, db=db)

    assert res["stage"] == PipelineStage.FILES_REVIEW
    assert res["technical_data"] == {"checker": "chk", "solution_cpp": "sol"}
    assert res["generated_sections"] == []
    files = await get_all_file_contents(db, task_session.id)
    assert files["checker"] == "chk"


@pytest.mark.asyncio
async def test_approve_interactive_generates_interaction(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "P"}
    task_session.problem_type = ProblemType.INTERACTIVE
    await db.commit()

    async def fake_interaction(stmt, model):
        return "interaction text"

    async def fake_pack(problem_type, stmt, model):
        return {"interactor": "int"}

    monkeypatch.setattr(mod.interaction_gen, "generate", fake_interaction)
    monkeypatch.setattr(mod.file_gen, "generate_pack", fake_pack)

    req = ApproveStatementRequest(session_id=task_session.id)
    res = await approve_statement(req, user_id=user.id, db=db)
    assert "Взаимодействие" in res["generated_sections"]
    assert res["statement"]["interaction"] == "interaction text"


@pytest.mark.asyncio
async def test_approve_with_groups_generates_scoring(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "P"}
    await db.commit()

    async def fake_scoring(stmt, model, enable_groups, enable_points, problem_type):
        return "scoring section"

    async def fake_pack(problem_type, stmt, model):
        return {"checker": "c"}

    monkeypatch.setattr(mod.scoring_gen, "generate", fake_scoring)
    monkeypatch.setattr(mod.file_gen, "generate_pack", fake_pack)

    req = ApproveStatementRequest(
        session_id=task_session.id, problem_settings={"enable_groups": True}
    )
    res = await approve_statement(req, user_id=user.id, db=db)
    assert "Система оценки" in res["generated_sections"]
    assert res["statement"]["scoring"] == "scoring section"


@pytest.mark.asyncio
async def test_approve_wrong_stage_400(db, user, task_session):
    task_session.stage = PipelineStage.DONE
    await db.commit()
    req = ApproveStatementRequest(session_id=task_session.id)
    with pytest.raises(HTTPException) as exc:
        await approve_statement(req, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_approve_generation_failure_marks_failed(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "P"}
    await db.commit()

    async def boom(*a, **k):
        raise RuntimeError("gen err")

    monkeypatch.setattr(mod.file_gen, "generate_pack", boom)

    req = ApproveStatementRequest(session_id=task_session.id)
    with pytest.raises(HTTPException) as exc:
        await approve_statement(req, user_id=user.id, db=db)
    assert exc.value.status_code == 500
    await db.refresh(task_session)
    assert task_session.stage == PipelineStage.FAILED


@pytest.mark.asyncio
async def test_approve_404(db, user):
    req = ApproveStatementRequest(session_id="nope")
    with pytest.raises(HTTPException) as exc:
        await approve_statement(req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
