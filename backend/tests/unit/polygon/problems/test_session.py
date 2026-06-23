"""Unit tests for api/user/polygon/problems/session.py route handlers."""
import pytest
from sqlalchemy import func, select

from api.user.polygon.problems.session import (
    UpdateSessionRequest,
    _session_to_dict,
    route_get_session,
    route_update_session_settings,
)
from models.task.session import TaskSession


def test_session_to_dict(task_session):
    out = _session_to_dict(task_session)
    assert out["session_id"] == task_session.id
    assert out["model"] == task_session.model
    assert "problem_settings" in out
    assert "statement" in out


@pytest.mark.asyncio
async def test_route_get_session_returns_existing(db, user, task_session):
    result = await route_get_session(polygon_id=555, user_id=user.id, db=db)
    assert result["session_id"] == task_session.id


@pytest.mark.asyncio
async def test_route_get_session_creates_when_missing(db, user):
    # No task_session fixture -> none exists for polygon_id=900.
    result = await route_get_session(polygon_id=900, user_id=user.id, db=db)
    assert result["session_id"]
    count = (
        await db.execute(
            select(func.count()).select_from(TaskSession).where(
                TaskSession.polygon_problem_id == 900,
                TaskSession.user_id == user.id,
            )
        )
    ).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_route_update_session_settings_existing(db, user, task_session):
    body = UpdateSessionRequest(model="new-model", system_prompt="hello")
    result = await route_update_session_settings(
        polygon_id=555, body=body, user_id=user.id, db=db
    )
    assert result["model"] == "new-model"
    assert result["system_prompt"] == "hello"


@pytest.mark.asyncio
async def test_route_update_session_settings_creates_when_missing(db, user):
    body = UpdateSessionRequest(model="m2", system_prompt="sp")
    result = await route_update_session_settings(
        polygon_id=901, body=body, user_id=user.id, db=db
    )
    assert result["model"] == "m2"
    assert result["system_prompt"] == "sp"
    row = (
        await db.execute(
            select(TaskSession).where(TaskSession.polygon_problem_id == 901)
        )
    ).scalars().first()
    assert row is not None


@pytest.mark.asyncio
async def test_route_update_session_settings_partial(db, user, task_session):
    original_prompt = task_session.system_prompt
    body = UpdateSessionRequest(model="only-model")
    result = await route_update_session_settings(
        polygon_id=555, body=body, user_id=user.id, db=db
    )
    assert result["model"] == "only-model"
    assert result["system_prompt"] == original_prompt
