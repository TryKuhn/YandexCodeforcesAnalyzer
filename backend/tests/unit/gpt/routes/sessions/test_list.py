"""Unit tests for routes.sessions.list.list_sessions."""
from datetime import datetime

import pytest

from api.user.gpt.routes.sessions.list import list_sessions
from models.task.session import PipelineStage, ProblemType, TaskSession


@pytest.mark.asyncio
async def test_list_empty(db, user):
    assert await list_sessions(user_id=user.id, db=db) == []


@pytest.mark.asyncio
async def test_list_returns_user_sessions_with_name(db, user, task_session):
    task_session.statement = {"name": "Named"}
    await db.commit()

    res = await list_sessions(user_id=user.id, db=db)
    assert len(res) == 1
    assert res[0]["session_id"] == task_session.id
    assert res[0]["name"] == "Named"
    assert res[0]["polygon_problem_id"] == 555


@pytest.mark.asyncio
async def test_list_draft_name_when_no_statement(db, user, task_session):
    res = await list_sessions(user_id=user.id, db=db)
    assert res[0]["name"] == "Черновик"


@pytest.mark.asyncio
async def test_list_excludes_other_users(db, user, task_session):
    other = TaskSession(
        id="other", user_id=user.id + 999, model="m", system_prompt="",
        history=[], problem_type=ProblemType.REGULAR, stage=PipelineStage.STATEMENT,
        progress={}, problem_settings={}, created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    db.add(other)
    await db.commit()
    res = await list_sessions(user_id=user.id, db=db)
    ids = {r["session_id"] for r in res}
    assert "other" not in ids
