"""Unit tests for api/user/polygon/problems/tags.py route handlers."""
import pytest

import api.user.polygon.problems.tags as mod
from api.pydantic_schemas.user.polygon_task import UpdateTagsRequest
from api.user.polygon.problems.tags import route_get_tags, route_set_tags


@pytest.mark.asyncio
async def test_route_get_tags(monkeypatch, db, user):
    async def fake_view_tags(problem_id, user_id, db):
        return ["dp", "greedy"]

    monkeypatch.setattr(mod, "view_tags", fake_view_tags)
    result = await route_get_tags(polygon_id=555, user_id=user.id, db=db)
    assert result == {"tags": ["dp", "greedy"]}


@pytest.mark.asyncio
async def test_route_set_tags_joins_tags(monkeypatch, db, user):
    captured = {}

    async def fake_set_tags(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(mod, "set_tags", fake_set_tags)
    body = UpdateTagsRequest(tags=["dp", "math", "greedy"])
    result = await route_set_tags(polygon_id=555, body=body, user_id=user.id, db=db)
    assert result == {"ok": True}
    assert captured["tags"] == "dp,math,greedy"
    assert captured["problem_id"] == 555
