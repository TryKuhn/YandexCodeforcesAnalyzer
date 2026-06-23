"""Unit tests for api/user/polygon/problems/list.py route handler + helpers."""
from datetime import datetime

import pytest

import api.user.polygon.problems.list as mod
from api.user.polygon.problems.list import (
    _get_statement_names,
    _serialize,
    route_list_problems,
)
from models.task.problem import PolygonProblem
from models.task.statement import PolygonStatement


async def _seed_problem(db, user, polygon_id, name="prob", deleted=False):
    p = PolygonProblem(
        user_id=user.id,
        polygon_id=polygon_id,
        owner="owner",
        name=name,
        deleted=deleted,
        list_fetched_at=datetime(2026, 1, 1),
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


def test_serialize_with_and_without_dates():
    p = PolygonProblem(
        user_id=1, polygon_id=10, owner="o", name="n",
        list_fetched_at=datetime(2026, 1, 1), info_fetched_at=None,
    )
    out = _serialize(p, "Statement Name")
    assert out["polygon_id"] == 10
    assert out["statement_name"] == "Statement Name"
    assert out["list_fetched_at"] == "2026-01-01T00:00:00"
    assert out["info_fetched_at"] is None


@pytest.mark.asyncio
async def test_get_statement_names_prefers_russian(db, user):
    p = await _seed_problem(db, user, 10)
    db.add(PolygonStatement(problem_id=p.id, lang="english", name="English"))
    db.add(PolygonStatement(problem_id=p.id, lang="russian", name="Russian"))
    await db.commit()
    result = await _get_statement_names(db, [p.id])
    assert result[p.id] == "Russian"


@pytest.mark.asyncio
async def test_get_statement_names_empty():
    assert await _get_statement_names(None, []) == {}


@pytest.mark.asyncio
async def test_route_list_problems_no_refresh(db, user):
    await _seed_problem(db, user, 10, name="alpha")
    await _seed_problem(db, user, 11, name="beta")

    result = await route_list_problems(
        refresh=False, show_deleted=False, page=1, per_page=20,
        search="", user_id=user.id, db=db,
    )
    assert result["total"] == 2
    assert result["page"] == 1
    assert {i["polygon_id"] for i in result["items"]} == {10, 11}
    # descending order by polygon_id
    assert result["items"][0]["polygon_id"] == 11


@pytest.mark.asyncio
async def test_route_list_problems_refresh_calls_list(monkeypatch, db, user):
    called = {}

    async def fake_list_problems(user_id, db, show_deleted):
        called["yes"] = (user_id, show_deleted)

    monkeypatch.setattr(mod, "list_problems", fake_list_problems)
    result = await route_list_problems(
        refresh=True, show_deleted=False, page=1, per_page=20,
        search="", user_id=user.id, db=db,
    )
    assert called["yes"] == (user.id, False)
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_route_list_problems_search_by_name(db, user):
    await _seed_problem(db, user, 10, name="apples")
    await _seed_problem(db, user, 11, name="oranges")

    result = await route_list_problems(
        refresh=False, show_deleted=False, page=1, per_page=20,
        search="apple", user_id=user.id, db=db,
    )
    assert result["total"] == 1
    assert result["items"][0]["name"] == "apples"
    assert result["search"] == "apple"


@pytest.mark.asyncio
async def test_route_list_problems_excludes_deleted(db, user):
    await _seed_problem(db, user, 10, name="live")
    await _seed_problem(db, user, 11, name="gone", deleted=True)

    result = await route_list_problems(
        refresh=False, show_deleted=False, page=1, per_page=20,
        search="", user_id=user.id, db=db,
    )
    assert result["total"] == 1
    assert result["items"][0]["polygon_id"] == 10


@pytest.mark.asyncio
async def test_route_list_problems_pagination(db, user):
    for pid in range(1, 6):
        await _seed_problem(db, user, pid, name=f"p{pid}")

    result = await route_list_problems(
        refresh=False, show_deleted=False, page=2, per_page=2,
        search="", user_id=user.id, db=db,
    )
    assert result["total"] == 5
    assert result["page"] == 2
    assert result["per_page"] == 2
    assert result["total_pages"] == 3
    assert len(result["items"]) == 2
