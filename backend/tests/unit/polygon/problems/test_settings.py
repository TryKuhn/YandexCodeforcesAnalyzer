"""Unit tests for api/user/polygon/problems/settings.py route handlers."""
import pytest

import api.user.polygon.problems.settings as mod
from api.user.polygon.problems.settings import (
    EnableGroupsBody,
    EnablePointsBody,
    route_enable_groups,
    route_enable_points,
)


@pytest.mark.asyncio
async def test_route_enable_groups(monkeypatch, db, user):
    captured = {}

    async def fake_enable_groups(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(mod, "enable_groups", fake_enable_groups)
    body = EnableGroupsBody(enable=True, testset="tests")
    result = await route_enable_groups(polygon_id=555, body=body, user_id=user.id, db=db)
    assert result == {"ok": True}
    assert captured["enable"] is True
    assert captured["test_set"] == "tests"
    assert captured["problem_id"] == 555


@pytest.mark.asyncio
async def test_route_enable_points(monkeypatch, db, user):
    captured = {}

    async def fake_enable_points(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(mod, "enable_points", fake_enable_points)
    body = EnablePointsBody(enable=False)
    result = await route_enable_points(polygon_id=555, body=body, user_id=user.id, db=db)
    assert result == {"ok": True}
    assert captured["enable"] is False
    assert captured["problem_id"] == 555
