"""Unit tests for api/user/polygon/problems/create.py route handler."""
import pytest
from sqlalchemy import func, select

import api.user.polygon.problems.create as mod
from api.pydantic_schemas.user.polygon_task import CreatePolygonProblemRequest
from api.user.polygon.problems.create import route_create_problem
from models.task.session import TaskSession


@pytest.mark.asyncio
async def test_route_create_problem_creates_clean_problem(monkeypatch, db, user):
    captured = {}

    async def fake_create_problem(name, user_id, db):
        captured["name"] = name
        captured["user_id"] = user_id
        return 777

    monkeypatch.setattr(mod, "create_problem", fake_create_problem)

    body = CreatePolygonProblemRequest(name="my-problem")
    result = await route_create_problem(body=body, user_id=user.id, db=db)

    assert result == {"polygon_id": 777, "name": "my-problem"}
    assert captured == {"name": "my-problem", "user_id": user.id}
    # the AI workspace now lives in the AI authoring service, not in ai_sessions
    assert (await db.execute(select(func.count()).select_from(TaskSession))).scalar() == 0
