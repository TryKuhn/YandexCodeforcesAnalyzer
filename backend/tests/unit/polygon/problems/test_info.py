"""Unit tests for api/user/polygon/problems/info.py route handlers."""
from datetime import datetime

import pytest

import api.user.polygon.problems.info as mod
from api.pydantic_schemas.user.polygon_task import UpdateInfoRequest
from api.user.polygon.problems.info import route_get_info, route_update_info
from models.task.problem import PolygonProblem


async def _seed(db, user, info_fetched=True):
    p = PolygonProblem(
        user_id=user.id,
        polygon_id=555,
        owner="o",
        name="n",
        input_file="input.txt",
        output_file="output.txt",
        interactive=False,
        well_formed=True,
        time_limit=1500,
        memory_limit=128,
        info_fetched_at=datetime(2026, 1, 1) if info_fetched else None,
    )
    db.add(p)
    await db.commit()
    return p


@pytest.mark.asyncio
async def test_route_get_info_from_cache(db, user):
    await _seed(db, user, info_fetched=True)
    result = await route_get_info(polygon_id=555, user_id=user.id, db=db)
    assert result["inputFile"] == "input.txt"
    assert result["outputFile"] == "output.txt"
    assert result["timeLimit"] == 1500
    assert result["memoryLimit"] == 128
    assert result["wellFormed"] is True


@pytest.mark.asyncio
async def test_route_get_info_falls_back_when_not_fetched(monkeypatch, db, user):
    await _seed(db, user, info_fetched=False)

    async def fake_get_problem_info(problem_id, user_id, db):
        return {"inputFile": "live"}

    monkeypatch.setattr(mod, "get_problem_info", fake_get_problem_info)
    result = await route_get_info(polygon_id=555, user_id=user.id, db=db)
    assert result == {"inputFile": "live"}


@pytest.mark.asyncio
async def test_route_get_info_falls_back_when_no_cache(monkeypatch, db, user):
    async def fake_get_problem_info(problem_id, user_id, db):
        return {"inputFile": "fetched"}

    monkeypatch.setattr(mod, "get_problem_info", fake_get_problem_info)
    result = await route_get_info(polygon_id=12345, user_id=user.id, db=db)
    assert result == {"inputFile": "fetched"}


@pytest.mark.asyncio
async def test_route_update_info(monkeypatch, db, user):
    captured = {}

    async def fake_update_info(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(mod, "update_info", fake_update_info)
    body = UpdateInfoRequest(
        input_file="in", output_file="out", interactive=True,
        time_limit=3000, memory_limit=512,
    )
    result = await route_update_info(polygon_id=555, body=body, user_id=user.id, db=db)
    assert result == {"ok": True}
    assert captured["input_file_name"] == "in"
    assert captured["output_file_name"] == "out"
    assert captured["interactive"] is True
    assert captured["time_limit"] == 3000
    assert captured["memory_limit"] == 512
