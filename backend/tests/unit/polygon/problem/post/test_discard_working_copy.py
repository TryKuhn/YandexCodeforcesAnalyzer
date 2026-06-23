import api.user.polygon.problem.post.discard_working_copy as mod
from api.user.polygon.problem.post.discard_working_copy import discard_working_copy


def _patch(monkeypatch, user, ret={"ok": True}):
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


async def test_discard_working_copy(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    result = await discard_working_copy(42, user.id, db)

    assert cap["method"] == "problem.discardWorkingCopy"
    assert cap["params"] == {"problemId": "42"}
    assert cap["user"] is user
    assert result == {"ok": True}
