"""Cache-update branch tests for api/user/polygon/problem/get/info.py."""
import pytest

import api.user.polygon.problem.get.info as mod
from api.user.polygon.problem.get.info import get_problem_info
from models.task.problem import PolygonProblem


def _patch(monkeypatch, user, ret):
    async def fake_get_user(user_id, db):
        return user

    async def fake_polygon_call(method_name, params, u):
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)


@pytest.mark.asyncio
async def test_get_problem_info_updates_cache(monkeypatch, db, user):
    p = PolygonProblem(user_id=user.id, polygon_id=42, owner="o", name="n")
    db.add(p)
    await db.commit()

    info = {
        "inputFile": "input.txt",
        "outputFile": "output.txt",
        "interactive": True,
        "wellFormed": True,
        "timeLimit": 3000,
        "memoryLimit": 512,
    }
    _patch(monkeypatch, user, info)
    result = await get_problem_info(42, user.id, db)
    assert result == info

    await db.refresh(p)
    assert p.input_file == "input.txt"
    assert p.output_file == "output.txt"
    assert p.interactive is True
    assert p.well_formed is True
    assert p.time_limit == 3000
    assert p.memory_limit == 512
    assert p.info_fetched_at is not None


@pytest.mark.asyncio
async def test_get_problem_info_dict_no_cached_row(monkeypatch, db, user):
    # dict return but no cached PolygonProblem -> no crash, returns info as-is.
    info = {"inputFile": "x"}
    _patch(monkeypatch, user, info)
    result = await get_problem_info(9999, user.id, db)
    assert result == info
