"""Unit tests for routes.files.manual_fix.manual_fix_file."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import ManualFixRequest
from api.user.gpt.routes.files.manual_fix import manual_fix_file
from api.user.gpt.services.ai_file_helpers import get_all_file_contents


@pytest.mark.asyncio
async def test_manual_fix_saves_and_clears_error(db, user, task_session):
    task_session.upload_errors = {"checker": {"error": "boom"}, "validator": {"error": "x"}}
    await db.commit()

    req = ManualFixRequest(
        session_id=task_session.id, file_key="checker", new_content="fixed code"
    )
    res = await manual_fix_file(req, user_id=user.id, db=db)
    assert res["file_key"] == "checker"
    assert res["remaining_errors"] == ["validator"]

    files = await get_all_file_contents(db, task_session.id)
    assert files["checker"] == "fixed code"
    await db.refresh(task_session)
    assert "checker" not in task_session.upload_errors


@pytest.mark.asyncio
async def test_manual_fix_404(db, user):
    req = ManualFixRequest(session_id="nope", file_key="checker", new_content="x")
    with pytest.raises(HTTPException) as exc:
        await manual_fix_file(req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
