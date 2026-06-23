"""Unit tests for routes.build.progress.get_upload_progress."""
import pytest
from fastapi import HTTPException

from api.user.gpt.routes.build.progress import get_upload_progress
from api.user.gpt.services.ai_file_helpers import upsert_ai_file


@pytest.mark.asyncio
async def test_progress_happy(db, user, task_session):
    task_session.progress = {"status": "building", "current_step": "step", "retries": 2}
    task_session.upload_errors = {"checker": {"error": "x"}}
    await db.commit()
    await upsert_ai_file(db, task_session.id, "checker", "code")
    await db.commit()

    res = await get_upload_progress(task_session.id, user_id=user.id, db=db)
    assert res["status"] == "building"
    assert res["current_step"] == "step"
    assert res["retries"] == 2
    assert res["upload_errors"] == {"checker": {"error": "x"}}
    assert res["polygon_problem_id"] == 555
    assert res["technical_data"] == {"checker": "code"}


@pytest.mark.asyncio
async def test_progress_defaults_idle(db, user, task_session):
    task_session.progress = {}
    await db.commit()
    res = await get_upload_progress(task_session.id, user_id=user.id, db=db)
    assert res["status"] == "idle"
    assert res["current_step"] is None


@pytest.mark.asyncio
async def test_progress_404(db, user):
    with pytest.raises(HTTPException) as exc:
        await get_upload_progress("nope", user_id=user.id, db=db)
    assert exc.value.status_code == 404
