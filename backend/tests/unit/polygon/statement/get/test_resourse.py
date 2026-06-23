import api.user.polygon.statement.get.resourse as mod
from api.user.polygon.statement.get.resourse import get_statement_resources


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


async def test_get_statement_resources(monkeypatch, db, user):
    ret = {"ok": True}
    cap = _patch(monkeypatch, user, ret)

    result = await get_statement_resources(33, user.id, db)

    assert cap["method"] == "problem.statementResources"
    assert cap["params"] == {"problemId": "33"}
    assert result is ret
