"""Unit tests for api/user/polygon/problems/info.py route handlers."""
from datetime import datetime

from api.pydantic_schemas.user.polygon_task import UpdateInfoRequest
from api.user.polygon.problems.info import route_get_info, route_update_info
from models.task.problem import PolygonProblem


async def _seed(db, user, info_fetched=True):
    p = PolygonProblem(
        user_id=user.id, polygon_id=555, owner="o", name="n",
        input_file="input.txt", output_file="output.txt", interactive=False,
        well_formed=True, time_limit=1500, memory_limit=128,
        info_fetched_at=datetime(2026, 1, 1) if info_fetched else None,
    )
    db.add(p)
    await db.commit()
    return p


async def test_route_get_info_from_cache(polygon_api, db, user):
    await _seed(db, user, info_fetched=True)
    result = await route_get_info(polygon_id=555, user_id=user.id, db=db)
    assert result == {
        "inputFile": "input.txt", "outputFile": "output.txt", "interactive": False,
        "timeLimit": 1500, "memoryLimit": 128, "wellFormed": True,
    }
    assert polygon_api.calls == []


async def test_route_get_info_falls_back_when_not_fetched(polygon_api, db, user):
    await _seed(db, user, info_fetched=False)
    polygon_api.respond("problem.info", {"inputFile": "live"})
    assert await route_get_info(polygon_id=555, user_id=user.id, db=db) == {"inputFile": "live"}


async def test_route_get_info_falls_back_when_no_cache(polygon_api, db, user):
    polygon_api.respond("problem.info", {"inputFile": "fetched"})
    result = await route_get_info(polygon_id=12345, user_id=user.id, db=db)
    assert result == {"inputFile": "fetched"}


async def test_route_get_info_refresh_bypasses_cache(polygon_api, db, user):
    await _seed(db, user, info_fetched=True)
    polygon_api.respond("problem.info", {"timeLimit": 4000})
    result = await route_get_info(polygon_id=555, refresh=True, user_id=user.id, db=db)
    assert result == {"timeLimit": 4000}


async def test_route_update_info_sends_all_fields_and_refreshes(polygon_api, db, user):
    p = await _seed(db, user)
    polygon_api.respond("problem.info", {"inputFile": "in", "outputFile": "out",
                                         "interactive": True, "wellFormed": False,
                                         "timeLimit": 3000, "memoryLimit": 512})
    body = UpdateInfoRequest(
        input_file="in", output_file="out", interactive=True, well_formed=False,
        time_limit=3000, memory_limit=512,
    )
    result = await route_update_info(polygon_id=555, body=body, user_id=user.id, db=db)
    assert result == {"ok": True}
    assert polygon_api.methods == ["problem.updateInfo", "problem.info"]
    assert polygon_api.calls[0].params == {
        "problemId": "555", "inputFile": "in", "outputFile": "out",
        "interactive": "true", "wellFormed": "false",  # wellFormed used to be dropped
        "timeLimit": "3000", "memoryLimit": "512",
    }
    await db.refresh(p)
    assert (p.time_limit, p.well_formed) == (3000, False)


async def test_route_update_info_skips_empty_and_zero_like_before(polygon_api, db, user):
    polygon_api.respond("problem.info", {})
    body = UpdateInfoRequest(input_file="", output_file="", time_limit=0, memory_limit=0,
                             interactive=False)
    await route_update_info(polygon_id=555, body=body, user_id=user.id, db=db)
    assert polygon_api.calls[0].params == {"problemId": "555", "interactive": "false"}
