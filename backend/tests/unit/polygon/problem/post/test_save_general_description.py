import api.user.polygon.problem.post.save_general_description as mod
from api.user.polygon.problem.post.save_general_description import (
    save_general_description,
)


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


async def test_save_general_description(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    result = await save_general_description(42, "desc text", user.id, db)

    assert cap["method"] == "problem.saveGeneralDescription"
    assert cap["params"] == {"problemId": "42", "description": "desc text"}
    assert cap["user"] is user
    assert result == {"ok": True}
