"""Unit tests for api/user/polygon/problems/tags.py route handlers."""
from api.pydantic_schemas.user.polygon_task import UpdateTagsRequest
from api.user.polygon.problems.tags import route_get_tags, route_set_tags


async def test_route_get_tags(polygon_api, db, user):
    polygon_api.respond("problem.viewTags", ["dp", "graphs"])
    assert await route_get_tags(polygon_id=555, user_id=user.id, db=db) == {
        "tags": ["dp", "graphs"]}


async def test_route_set_tags_joins_tags(polygon_api, db, user):
    body = UpdateTagsRequest(tags=["dp", "graphs"])
    assert await route_set_tags(polygon_id=555, body=body, user_id=user.id, db=db) == {
        "ok": True}
    assert polygon_api.last().params == {"problemId": "555", "tags": "dp,graphs"}
