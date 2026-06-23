import api.user.polygon.test_group.get.view as mod
from api.user.polygon.test_group.get.view import view_test_group


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


async def test_view_test_group_without_group(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)

    await view_test_group(8, "tests", user.id, db)

    assert cap["method"] == "problem.viewTestGroup"
    assert cap["params"] == {"problemId": "8", "testset": "tests"}
    assert "group" not in cap["params"]


async def test_view_test_group_with_group(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)

    await view_test_group(8, "tests", user.id, db, group="g1")

    assert cap["params"]["group"] == "g1"
    assert cap["params"]["testset"] == "tests"
