"""Unit tests for api/user/polygon/problems/packages.py route handlers."""
from api.user.polygon.problems.packages import (BuildPackageRequest,
                                                route_build_package,
                                                route_download_package,
                                                route_get_packages)


async def test_route_get_packages(polygon_api, db, user):
    polygon_api.respond("problem.packages", [{"id": 1, "state": "READY"}])
    assert await route_get_packages(polygon_id=555, user_id=user.id, db=db) == [
        {"id": 1, "state": "READY"}]


async def test_route_build_package_commits_then_builds_with_flags(polygon_api, db, user):
    polygon_api.respond("problem.commitChanges", {"committed": True})
    body = BuildPackageRequest(full=False, verify=True)
    result = await route_build_package(polygon_id=555, body=body, user_id=user.id, db=db)
    assert result == {"status": "building"}
    assert polygon_api.methods == ["problem.commitChanges", "problem.buildPackage"]
    assert polygon_api.calls[0].params == {
        "problemId": "555", "minorChanges": "true", "message": "manual commit"}
    # The body's flags are honoured (they used to be ignored).
    assert polygon_api.calls[1].params == {
        "problemId": "555", "full": "false", "verify": "true"}


async def test_route_build_package_defaults_full_verified(polygon_api, db, user):
    polygon_api.respond("problem.commitChanges", {})
    await route_build_package(polygon_id=555, body=BuildPackageRequest(), user_id=user.id, db=db)
    assert polygon_api.last().params == {"problemId": "555", "full": "true", "verify": "true"}


async def test_route_build_package_without_commit(polygon_api, db, user):
    await route_build_package(
        polygon_id=555, body=BuildPackageRequest(commit=False), user_id=user.id, db=db
    )
    assert polygon_api.methods == ["problem.buildPackage"]


async def test_route_download_package(polygon_api, db, user):
    polygon_api.respond("problem.package", b"PK\x03\x04")
    response = await route_download_package(
        polygon_id=555, package_id=9, type="linux", user_id=user.id, db=db
    )
    assert response.body == b"PK\x03\x04"
    assert response.media_type == "application/zip"
    assert "problem-555-9-linux.zip" in response.headers["content-disposition"]
    assert polygon_api.last().params == {"problemId": "555", "packageId": "9", "type": "linux"}
