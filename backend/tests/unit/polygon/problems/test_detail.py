"""Unit tests for api/user/polygon/problems/detail.py route handlers."""
import pytest
from fastapi import HTTPException

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
async def test_route_get_problem_populates_via_list(polygon_api, db, user):
    # No cache initially; problems.list seeds it so the second lookup succeeds.
    polygon_api.respond("problems.list", [{"id": 999, "owner": "o", "name": "new"}])
    result = await route_get_problem(polygon_id=999, user_id=user.id, db=db)
    assert result["polygon_id"] == 999
    assert result["name"] == "new"


@pytest.mark.asyncio
async def test_route_get_problem_404(polygon_api, db, user):
    polygon_api.respond("problems.list", [])
    with pytest.raises(HTTPException) as exc:
        await route_get_problem(polygon_id=12345, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_route_sync_problem_refreshes_info_and_statements(polygon_api, db, user):
    p = await _seed_problem(db, user)
    polygon_api.respond("problem.info", {"timeLimit": 3000, "memoryLimit": 64})
    polygon_api.respond("problem.statements", {"russian": {"name": "Имя"}})

    result = await route_sync_problem(polygon_id=555, user_id=user.id, db=db)
    assert result == {"ok": True}
    assert polygon_api.methods == ["problem.info", "problem.statements"]
    await db.refresh(p)
    assert (p.time_limit, p.memory_limit) == (3000, 64)
