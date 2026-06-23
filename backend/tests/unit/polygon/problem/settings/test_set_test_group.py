import api.user.polygon.problem.settings.set_test_group as mod
from api.user.polygon.problem.settings.set_test_group import set_test_group


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


async def test_set_test_group(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    result = await set_test_group(42, "tests", "1", "1,2,3", user.id, db)

    assert cap["method"] == "problem.setTestGroup"
    assert cap["params"] == {
        "problemId": "42",
        "testset": "tests",
        "testGroup": "1",
        "testIndices": "1,2,3",
    }
    assert cap["user"] is user
    assert result == {"ok": True}
