"""Unit tests for routes.statement.generate_scoring.generate_scoring."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import GenerateScoringRequest
from api.user.gpt.routes.statement import generate_scoring as mod
from api.user.gpt.routes.statement.generate_scoring import generate_scoring
from models.task.session import ProblemType


@pytest.mark.asyncio
async def test_scoring_output_only_uses_scoring_gen(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "P"}
    task_session.problem_type = ProblemType.OUTPUT_ONLY
    await db.commit()

    async def fake_scoring(statement, model, enable_groups, enable_points, problem_type):
        return "OUTPUT SCORING"

    called = {"subtask": False}

    async def fake_subtask(*a, **k):
        called["subtask"] = True
        return []

    monkeypatch.setattr(mod.scoring_gen, "generate", fake_scoring)
    monkeypatch.setattr(mod.subtask_plan_gen, "generate", fake_subtask)

    req = GenerateScoringRequest(session_id=task_session.id)
    res = await generate_scoring(req, user_id=user.id, db=db)
    assert res["scoring"] == "OUTPUT SCORING"
    assert called["subtask"] is False
    await db.refresh(task_session)
    assert task_session.statement["scoring"] == "OUTPUT SCORING"


@pytest.mark.asyncio
async def test_scoring_groups_path_uses_subtask_plan(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "P"}
    task_session.problem_settings = {"enable_groups": True}
    await db.commit()

    async def fake_subtask(statement, model):
        return [{"points": 50}, {"points": 50}]

    monkeypatch.setattr(mod.subtask_plan_gen, "generate", fake_subtask)
    monkeypatch.setattr(
        mod.subtask_plan_gen, "render_scoring_latex", lambda subtasks: "LATEX TABLE"
    )

    req = GenerateScoringRequest(session_id=task_session.id)
    res = await generate_scoring(req, user_id=user.id, db=db)
    assert res["scoring"] == "LATEX TABLE"
    await db.refresh(task_session)
    assert task_session.problem_settings["subtasks"] == [{"points": 50}, {"points": 50}]
    assert task_session.problem_settings["enable_groups"] is True
    assert task_session.problem_settings["enable_points"] is True


@pytest.mark.asyncio
async def test_scoring_subtask_plan_empty_500(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "P"}
    task_session.problem_settings = {"enable_points": True}
    await db.commit()

    async def fake_subtask(statement, model):
        return []

    monkeypatch.setattr(mod.subtask_plan_gen, "generate", fake_subtask)

    req = GenerateScoringRequest(session_id=task_session.id)
    with pytest.raises(HTTPException) as exc:
        await generate_scoring(req, user_id=user.id, db=db)
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_scoring_disabled_400(db, user, task_session):
    task_session.statement = {"name": "P"}
    task_session.problem_settings = {}
    await db.commit()
    req = GenerateScoringRequest(session_id=task_session.id)
    with pytest.raises(HTTPException) as exc:
        await generate_scoring(req, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_scoring_no_statement_400(db, user, task_session):
    req = GenerateScoringRequest(session_id=task_session.id)
    with pytest.raises(HTTPException) as exc:
        await generate_scoring(req, user_id=user.id, db=db)
    assert exc.value.status_code == 400
