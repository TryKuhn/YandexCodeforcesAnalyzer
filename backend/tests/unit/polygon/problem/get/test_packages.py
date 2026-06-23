import api.user.polygon.problem.get.packages as mod
from api.user.polygon.problem.get.packages import get_packages


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


async def test_get_packages(monkeypatch, db, user):
    cap = _patch(monkeypatch, user, ret=[{"id": 1}])
    result = await get_packages(42, user.id, db)

    assert cap["method"] == "problem.packages"
    assert cap["params"] == {"problemId": "42"}
    assert cap["user_id"] == user.id
    assert cap["user"] is user
    assert result == [{"id": 1}]
