"""Unit tests for api/user/polygon/problems/settings.py route handlers."""
from api.pydantic_schemas.user.polygon_task import SaveTestGroupRequest
from api.user.polygon.problems.settings import (
    EnableGroupsBody, EnablePointsBody, route_enable_groups, route_enable_points,
    route_enable_treat_points_as_percent, route_save_test_group,
    route_view_test_groups)


async def test_route_enable_groups(polygon_api, db, user):
    body = EnableGroupsBody(enable=True, testset="tests")
    assert await route_enable_groups(polygon_id=555, body=body, user_id=user.id, db=db) == {
        "ok": True}
    assert polygon_api.last().params == {"problemId": "555", "testset": "tests", "enable": "true"}


async def test_route_enable_points(polygon_api, db, user):
    await route_enable_points(polygon_id=555, body=EnablePointsBody(enable=False),
                              user_id=user.id, db=db)
    assert polygon_api.last().params == {"problemId": "555", "enable": "false"}


async def test_route_treat_points_as_percent(polygon_api, db, user):
    await route_enable_treat_points_as_percent(
        polygon_id=555, body=EnablePointsBody(enable=True), user_id=user.id, db=db
    )
    assert polygon_api.last().method == "problem.enableTreatPointsFromCheckerAsPercent"


async def test_route_view_and_save_test_group(polygon_api, db, user):
    polygon_api.respond("problem.viewTestGroup", [{"name": "1", "pointsPolicy": "EACH_TEST"}])
    groups = await route_view_test_groups(
        polygon_id=555, testset="tests", group=None, user_id=user.id, db=db
    )
    assert groups[0]["name"] == "1"

    body = SaveTestGroupRequest(points_policy="each_test", feedback_policy="points",
                                dependencies=["0"])
    await route_save_test_group(polygon_id=555, testset="tests", group="1", body=body,
                                user_id=user.id, db=db)
    assert polygon_api.last().params == {
        "problemId": "555", "testset": "tests", "group": "1",
        "pointsPolicy": "EACH_TEST", "feedbackPolicy": "POINTS", "dependencies": "0",
    }
