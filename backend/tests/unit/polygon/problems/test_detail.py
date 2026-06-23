"""Unit tests for api/user/polygon/problems/detail.py route handlers."""
import pytest
from fastapi import HTTPException

import api.user.polygon.problems.detail as mod
from api.user.polygon.problems.detail import route_get_problem, route_sync_problem
from models.task.problem import PolygonProblem
from models.task.test_group import PolygonTestGroup


async def _seed_problem(db, user, polygon_id=555):
    p = PolygonProblem(
        user_id=user.id,
        polygon_id=polygon_id,
        owner="owner",
        name="prob",
        time_limit=2000,
        memory_limit=256,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest.mark.asyncio
async def test_route_get_problem_from_cache(db, user):
    p = await _seed_problem(db, user)
    result = await route_get_problem(polygon_id=555, user_id=user.id, db=db)
    assert result["polygon_id"] == 555
    assert result["id"] == p.id
    assert result["enable_groups"] is False


@pytest.mark.asyncio
async def test_route_get_problem_with_test_groups(db, user):
    p = await _seed_problem(db, user)
    db.add(PolygonTestGroup(problem_id=p.id, testset="tests", name="g1"))
    await db.commit()
    result = await route_get_problem(polygon_id=555, user_id=user.id, db=db)
    assert result["enable_groups"] is True


@pytest.mark.asyncio
async def test_route_get_problem_populates_via_list(monkeypatch, db, user):
    # No cache initially; list_problems seeds it so the second lookup succeeds.
    async def fake_list_problems(user_id, db):
        await _seed_problem(db, user, polygon_id=999)

    monkeypatch.setattr(mod, "list_problems", fake_list_problems)
    result = await route_get_problem(polygon_id=999, user_id=user.id, db=db)
    assert result["polygon_id"] == 999


@pytest.mark.asyncio
async def test_route_get_problem_404(monkeypatch, db, user):
    async def fake_list_problems(user_id, db):
        return None  # does not seed anything

    monkeypatch.setattr(mod, "list_problems", fake_list_problems)
    with pytest.raises(HTTPException) as exc:
        await route_get_problem(polygon_id=12345, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_route_sync_problem(monkeypatch, db, user):
    calls = {}

    async def fake_get_problem_info(problem_id, user_id, db):
        calls["info"] = (problem_id, user_id)

    async def fake_get_statements(problem_id, user_id, db):
        calls["stmt"] = (problem_id, user_id)

    monkeypatch.setattr(mod, "get_problem_info", fake_get_problem_info)
    monkeypatch.setattr(mod, "get_statements", fake_get_statements)

    result = await route_sync_problem(polygon_id=555, user_id=user.id, db=db)
    assert result == {"ok": True}
    assert calls["info"] == (555, user.id)
    assert calls["stmt"] == (555, user.id)
