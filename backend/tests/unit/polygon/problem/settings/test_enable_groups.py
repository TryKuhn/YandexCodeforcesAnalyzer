import api.user.polygon.problem.settings.enable_groups as mod
from api.user.polygon.problem.settings.enable_groups import enable_groups


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


async def test_enable_groups_true(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    result = await enable_groups(42, "tests", True, user.id, db)

    assert cap["method"] == "problem.enableGroups"
    assert cap["params"] == {
        "problemId": "42",
        "testset": "tests",
        "enable": "true",
    }
    assert result == {"ok": True}


async def test_enable_groups_false(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await enable_groups(42, "tests", False, user.id, db)

    assert cap["params"]["enable"] == "false"
