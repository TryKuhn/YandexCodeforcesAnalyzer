"""Unit tests for routes.build.retry_after_manual_fix.retry_after_manual_fix_endpoint."""
import pytest
from fastapi import BackgroundTasks, HTTPException

from api.pydantic_schemas.user.ai_task import ApproveFilesRequest
from api.user.gpt.routes.build import retry_after_manual_fix as mod
from api.user.gpt.routes.build.retry_after_manual_fix import \
    retry_after_manual_fix_endpoint
from models.task.session import PipelineStage


@pytest.mark.asyncio
async def test_retry_starts_build(db, user, task_session, monkeypatch):
    task_session.stage = PipelineStage.FAILED
    task_session.upload_errors = {"checker": {"error": "x"}}
    await db.commit()

    monkeypatch.setattr(mod, "run_full_build", lambda sid: None)

    bg = BackgroundTasks()
    req = ApproveFilesRequest(session_id=task_session.id)
    res = await retry_after_manual_fix_endpoint(req, bg, user_id=user.id, db=db)
    assert res["status"] == "retry_started"
    assert len(bg.tasks) == 1
    await db.refresh(task_session)
    assert task_session.stage == PipelineStage.UPLOADING
    assert task_session.upload_errors == {}


@pytest.mark.asyncio
async def test_retry_wrong_stage_400(db, user, task_session):
    task_session.stage = PipelineStage.STATEMENT
    await db.commit()
    bg = BackgroundTasks()
    req = ApproveFilesRequest(session_id=task_session.id)
    with pytest.raises(HTTPException) as exc:
        await retry_after_manual_fix_endpoint(req, bg, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_retry_404(db, user):
    bg = BackgroundTasks()
    req = ApproveFilesRequest(session_id="nope")
    with pytest.raises(HTTPException) as exc:
        await retry_after_manual_fix_endpoint(req, bg, user_id=user.id, db=db)
    assert exc.value.status_code == 404
