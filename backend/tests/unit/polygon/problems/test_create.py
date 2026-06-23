"""Unit tests for api/user/polygon/problems/create.py route handler."""
import pytest
from sqlalchemy import select

import api.user.polygon.problems.create as mod
from api.pydantic_schemas.user.polygon_task import CreatePolygonProblemRequest
from api.user.polygon.problems.create import route_create_problem
from models.task.session import TaskSession


@pytest.mark.asyncio
async def test_route_create_problem_creates_session(monkeypatch, db, user):
    captured = {}

    async def fake_create_problem(name, user_id, db):
        captured["name"] = name
        captured["user_id"] = user_id
        return 777

    monkeypatch.setattr(mod, "create_problem", fake_create_problem)

    body = CreatePolygonProblemRequest(name="my-problem")
    result = await route_create_problem(body=body, user_id=user.id, db=db)

    assert result["polygon_id"] == 777
    assert result["name"] == "my-problem"
    assert result["session_id"]
    assert captured == {"name": "my-problem", "user_id": user.id}

    # A TaskSession row must have been persisted with the polygon id.
    row = (
        await db.execute(
            select(TaskSession).where(TaskSession.id == result["session_id"])
        )
    ).scalars().first()
    assert row is not None
    assert row.polygon_problem_id == 777
    assert row.user_id == user.id
    assert row.problem_settings["input_file"] == "stdin"
