"""Unit tests for routes.build.approve_files.approve_files."""
import pytest
from fastapi import BackgroundTasks, HTTPException

from api.pydantic_schemas.user.ai_task import ApproveFilesRequest
from api.user.gpt.routes.build import approve_files as mod
from api.user.gpt.routes.build.approve_files import approve_files
from api.user.gpt.services.ai_file_helpers import upsert_ai_file
from models.task.session import PipelineStage


@pytest.mark.asyncio
async def test_approve_files_starts_build(db, user, task_session, monkeypatch):
    task_session.stage = PipelineStage.FILES_REVIEW
    await db.commit()
    await upsert_ai_file(db, task_session.id, "checker", "code")
    await db.commit()

    monkeypatch.setattr(mod, "run_full_build", lambda sid: None)

    bg = BackgroundTasks()
    req = ApproveFilesRequest(session_id=task_session.id)
    res = await approve_files(req, bg, user_id=user.id, db=db)
    assert res["status"] == "upload_started"
    assert len(bg.tasks) == 1
    await db.refresh(task_session)
    assert task_session.stage == PipelineStage.UPLOADING


@pytest.mark.asyncio
async def test_approve_files_wrong_stage_400(db, user, task_session):
    task_session.stage = PipelineStage.DONE
    await db.commit()
    bg = BackgroundTasks()
    req = ApproveFilesRequest(session_id=task_session.id)
    with pytest.raises(HTTPException) as exc:
        await approve_files(req, bg, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_approve_files_no_files_400(db, user, task_session):
    task_session.stage = PipelineStage.FILES_REVIEW
    await db.commit()
    bg = BackgroundTasks()
    req = ApproveFilesRequest(session_id=task_session.id)
    with pytest.raises(HTTPException) as exc:
        await approve_files(req, bg, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_approve_files_404(db, user):
    bg = BackgroundTasks()
    req = ApproveFilesRequest(session_id="nope")
    with pytest.raises(HTTPException) as exc:
        await approve_files(req, bg, user_id=user.id, db=db)
    assert exc.value.status_code == 404
