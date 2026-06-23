"""Cache-upsert branch tests for api/user/polygon/files/solution/get/solutions.py."""
import pytest
from sqlalchemy import select

import api.user.polygon.files.solution.get.solutions as mod
from api.user.polygon.files.solution.get.solutions import get_solutions
from models.task.problem import PolygonProblem
from models.task.solution import PolygonSolution


def _patch(monkeypatch, user, ret):
    async def fake_get_user(user_id, db):
        return user

    async def fake_polygon_call(method_name, params, u):
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)


@pytest.mark.asyncio
async def test_get_solutions_inserts_and_updates(monkeypatch, db, user):
    p = PolygonProblem(user_id=user.id, polygon_id=42, owner="o", name="n")
    db.add(p)
    await db.commit()
    await db.refresh(p)
    # Pre-existing solution to exercise the update branch.
    db.add(PolygonSolution(
        problem_id=p.id, name="sol.cpp", content="", source_type="old", tag="OL"
    ))
    await db.commit()

    data = [
        {"name": "sol.cpp", "sourceType": "cpp.g++17", "tag": "MA"},
        {"name": "brute.cpp", "sourceType": "cpp.g++17", "tag": "TL"},
    ]
    _patch(monkeypatch, user, data)
    result = await get_solutions(42, user.id, db)
    assert result == data

    rows = (
        await db.execute(select(PolygonSolution).filter_by(problem_id=p.id))
    ).scalars().all()
    by_name = {r.name: r for r in rows}
    assert by_name["sol.cpp"].tag == "MA"
    assert by_name["sol.cpp"].source_type == "cpp.g++17"
    assert by_name["brute.cpp"].uploaded is True


@pytest.mark.asyncio
async def test_get_solutions_list_no_cached_problem(monkeypatch, db, user):
    # list return but no cached problem -> no rows written, returns list.
    data = [{"name": "x.cpp", "sourceType": "cpp", "tag": "MA"}]
    _patch(monkeypatch, user, data)
    result = await get_solutions(9999, user.id, db)
    assert result == data
    rows = (await db.execute(select(PolygonSolution))).scalars().all()
    assert rows == []
