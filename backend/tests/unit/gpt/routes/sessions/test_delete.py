"""Unit tests for routes.sessions.delete.delete_session."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from api.user.gpt.routes.sessions.delete import delete_session
from api.user.gpt.services.ai_file_helpers import upsert_ai_file
from models.task.generated_file import TaskGeneratedFile
from models.task.session import TaskSession


@pytest.mark.asyncio
async def test_delete_removes_session_and_files(db, user, task_session):
    await upsert_ai_file(db, task_session.id, "checker", "code")
    await db.commit()

    res = await delete_session(task_session.id, user_id=user.id, db=db)
    assert res == {"status": "deleted"}

    assert (await db.execute(select(TaskSession))).scalars().all() == []
    files = (await db.execute(select(TaskGeneratedFile))).scalars().all()
    assert files == []


@pytest.mark.asyncio
async def test_delete_missing_session_404(db, user):
    with pytest.raises(HTTPException) as exc:
        await delete_session("nope", user_id=user.id, db=db)
    assert exc.value.status_code == 404
