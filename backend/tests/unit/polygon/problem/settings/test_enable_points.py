import api.user.polygon.problem.settings.enable_points as mod
from api.user.polygon.problem.settings.enable_points import enable_points


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


async def test_enable_points_true(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    result = await enable_points(42, True, user.id, db)

    assert cap["method"] == "problem.enablePoints"
    assert cap["params"] == {"problemId": "42", "enable": "true"}
    assert result == {"ok": True}


async def test_enable_points_false(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await enable_points(42, False, user.id, db)

    assert cap["params"] == {"problemId": "42", "enable": "false"}
