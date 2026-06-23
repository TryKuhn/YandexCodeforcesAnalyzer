import api.user.polygon.problem.get.general_tutorial as mod
from api.user.polygon.problem.get.general_tutorial import view_general_tutorial


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


async def test_view_general_tutorial(monkeypatch, db, user):
    cap = _patch(monkeypatch, user, ret={"tutorial": "y"})
    result = await view_general_tutorial(42, user.id, db)

    assert cap["method"] == "problem.viewGeneralTutorial"
    assert cap["params"] == {"problemId": "42"}
    assert cap["user_id"] == user.id
    assert cap["user"] is user
    assert result == {"tutorial": "y"}
