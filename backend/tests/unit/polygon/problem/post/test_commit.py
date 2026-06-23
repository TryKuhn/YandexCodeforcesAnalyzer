import pytest
from fastapi import HTTPException

import api.user.polygon.problem.post.commit as mod
from api.user.polygon.problem.post.commit import commit_changes


def _patch(monkeypatch, user, ret):
    cap = {}

    async def fake_get_user(user_id, db):
        cap["user_id"] = user_id
        return user

    async def fake_polygon_call(method_name, params, u):
        cap["method"] = method_name
        cap["params"] = params
        cap["user"] = u
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)
    return cap


async def test_commit_changes_defaults(monkeypatch, db, user):
    cap = _patch(monkeypatch, user, ret={"ok": 1})
    result = await commit_changes(5, user.id, db)

    assert cap["method"] == "problem.commitChanges"
    assert cap["params"] == {"problemId": "5"}
    assert cap["user"] is user
    assert result == {"ok": 1}


async def test_commit_changes_with_options(monkeypatch, db, user):
    cap = _patch(monkeypatch, user, ret={"ok": 1})
    result = await commit_changes(
        5, user.id, db, minor_changes=True, message="msg"
    )

    assert cap["params"] == {
        "problemId": "5",
        "minorChanges": "true",
        "message": "msg",
    }
    assert result == {"ok": 1}


async def test_commit_changes_conflict_raises_409(monkeypatch, db, user):
    _patch(monkeypatch, user, ret={"conflictOccurred": True})

    with pytest.raises(HTTPException) as exc_info:
        await commit_changes(5, user.id, db)

    assert exc_info.value.status_code == 409
