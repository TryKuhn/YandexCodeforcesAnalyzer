"""Unit tests for api/user/polygon/problems/packages.py route handlers."""
import pytest

import api.user.polygon.problems.packages as mod
from api.user.polygon.problems.packages import (
    BuildPackageRequest,
    route_build_package,
    route_get_packages,
)


@pytest.mark.asyncio
async def test_route_get_packages(monkeypatch, db, user):
    async def fake_get_packages(problem_id, user_id, db):
        return [{"id": 1, "state": "READY"}]

    monkeypatch.setattr(mod, "get_packages", fake_get_packages)
    result = await route_get_packages(polygon_id=555, user_id=user.id, db=db)
    assert result == [{"id": 1, "state": "READY"}]


@pytest.mark.asyncio
async def test_route_build_package_commits_then_builds(monkeypatch, db, user):
    order = []

    async def fake_commit_changes(**kwargs):
        order.append(("commit", kwargs))

    async def fake_build_package(**kwargs):
        order.append(("build", kwargs))

    monkeypatch.setattr(mod, "commit_changes", fake_commit_changes)
    monkeypatch.setattr(mod, "build_package", fake_build_package)

    body = BuildPackageRequest(full=True, verify=True)
    result = await route_build_package(polygon_id=555, body=body, user_id=user.id, db=db)
    assert result == {"status": "building"}
    assert [o[0] for o in order] == ["commit", "build"]
    assert order[0][1]["minor_changes"] is True
    assert order[0][1]["message"] == "manual commit"
    assert order[1][1]["problem_id"] == 555
