import pytest
from fastapi import HTTPException

import api.user.polygon.files.solution.post.edit_extra_tags as mod
from api.user.polygon.files.solution.post.edit_extra_tags import (
    edit_solution_extra_tags,
)


def _patch(monkeypatch, user, ret={"ok": True}):
    cap = {}

    async def fake_get_user(user_id, db):
        cap["user_id"] = user_id
        return user

    async def fake_polygon_call(method_name, params, u):
        cap["method"] = method_name
        cap["params"] = params
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)
    return cap


async def test_edit_extra_tags_testset_no_remove(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)

    await edit_solution_extra_tags(
        5, "sol.cpp", False, user.id, db, testset="tests", tag="wa"
    )

    assert cap["method"] == "problem.editSolutionExtraTags"
    params = cap["params"]
    assert params["problemId"] == "5"
    assert params["name"] == "sol.cpp"
    assert params["remove"] == "false"
    assert params["testset"] == "tests"
    assert params["tag"] == "wa"
    assert "testGroup" not in params


async def test_edit_extra_tags_group_remove_omits_tag(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)

    await edit_solution_extra_tags(
        5, "sol.cpp", True, user.id, db, test_group="g1", tag="wa"
    )

    params = cap["params"]
    assert params["remove"] == "true"
    assert params["testGroup"] == "g1"
    assert "testset" not in params
    assert "tag" not in params  # omitted because remove is True


async def test_edit_extra_tags_both_none_raises(monkeypatch, db, user):
    _patch(monkeypatch, user)

    with pytest.raises(HTTPException) as exc:
        await edit_solution_extra_tags(5, "sol.cpp", False, user.id, db)

    assert exc.value.status_code == 400


async def test_edit_extra_tags_both_set_raises(monkeypatch, db, user):
    _patch(monkeypatch, user)

    with pytest.raises(HTTPException) as exc:
        await edit_solution_extra_tags(
            5, "sol.cpp", False, user.id, db, testset="tests", test_group="g1"
        )

    assert exc.value.status_code == 400
