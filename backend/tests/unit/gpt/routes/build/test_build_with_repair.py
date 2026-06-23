"""Unit tests for routes.build.build_with_repair.build_with_repair."""
import pytest
from fastapi import BackgroundTasks, HTTPException

from api.pydantic_schemas.user.ai_task import ApproveFilesRequest
from api.user.gpt.routes.build import build_with_repair as mod
from api.user.gpt.routes.build.build_with_repair import build_with_repair
from models.task.session import PipelineStage


@pytest.mark.asyncio
async def test_build_with_repair_starts(db, user, task_session, monkeypatch):
    monkeypatch.setattr(mod, "run_build_with_repair", lambda sid: None)

    bg = BackgroundTasks()
    req = ApproveFilesRequest(session_id=task_session.id)
    res = await build_with_repair(req, bg, user_id=user.id, db=db)
    assert res["status"] == "build_started"
    assert len(bg.tasks) == 1
    await db.refresh(task_session)
    assert task_session.stage == PipelineStage.BUILDING_PACKAGE


@pytest.mark.asyncio
async def test_build_with_repair_no_polygon_id_400(db, user, task_session):
    task_session.polygon_problem_id = None
    await db.commit()
    bg = BackgroundTasks()
    req = ApproveFilesRequest(session_id=task_session.id)
    with pytest.raises(HTTPException) as exc:
        await build_with_repair(req, bg, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_build_with_repair_404(db, user):
    bg = BackgroundTasks()
    req = ApproveFilesRequest(session_id="nope")
    with pytest.raises(HTTPException) as exc:
        await build_with_repair(req, bg, user_id=user.id, db=db)
    assert exc.value.status_code == 404
