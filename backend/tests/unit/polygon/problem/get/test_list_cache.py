"""Cache-upsert branch tests for api/user/polygon/problem/get/list.py."""
import pytest
from sqlalchemy import select

import api.user.polygon.problem.get.list as mod
from api.user.polygon.problem.get.list import list_problems
from models.task.problem import PolygonProblem


def _patch(monkeypatch, user, ret):
    captured = {}

    async def fake_get_user(user_id, db):
        return user

    async def fake_polygon_call(method_name, params, u):
        captured["method"] = method_name
        captured["params"] = params
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)
    return captured


@pytest.mark.asyncio
async def test_list_problems_inserts_new(monkeypatch, db, user):
    data = [
        {"id": 1, "owner": "o", "name": "p1", "accessType": "OWNER",
         "revision": 2, "workingCopyRevision": 3, "latestPackage": 4,
         "deleted": False, "favourite": True, "modified": True},
        {"id": None},  # skipped — no id
    ]
    cap = _patch(monkeypatch, user, data)
    result = await list_problems(user.id, db)
    assert result == data
    assert cap["method"] == "problems.list"

    rows = (await db.execute(select(PolygonProblem))).scalars().all()
    assert len(rows) == 1
    assert rows[0].polygon_id == 1
    assert rows[0].favourite is True
    assert rows[0].access_type == "OWNER"


@pytest.mark.asyncio
async def test_list_problems_updates_existing(monkeypatch, db, user):
    existing = PolygonProblem(user_id=user.id, polygon_id=5, owner="old", name="old")
    db.add(existing)
    await db.commit()

    data = [{"id": 5, "owner": "new", "name": "newname", "revision": 9}]
    _patch(monkeypatch, user, data)
    await list_problems(user.id, db)

    row = (
        await db.execute(select(PolygonProblem).filter_by(polygon_id=5))
    ).scalars().first()
    assert row.owner == "new"
    assert row.name == "newname"
    assert row.revision == 9


@pytest.mark.asyncio
async def test_list_problems_non_list_returns_empty(monkeypatch, db, user):
    _patch(monkeypatch, user, {"not": "a list"})
    result = await list_problems(user.id, db)
    assert result == []
    rows = (await db.execute(select(PolygonProblem))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_list_problems_passes_filter_params(monkeypatch, db, user):
    cap = _patch(monkeypatch, user, [])
    await list_problems(
        user.id, db, show_deleted=True, problem_id=7, name="nm", owner="ow"
    )
    assert cap["params"] == {
        "showDeleted": "true", "id": "7", "name": "nm", "owner": "ow"
    }
