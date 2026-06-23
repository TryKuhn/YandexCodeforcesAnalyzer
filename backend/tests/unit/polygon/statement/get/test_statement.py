import api.user.polygon.statement.get.setatement as mod
from api.user.polygon.statement.get.setatement import get_statements


def _patch(monkeypatch, user, ret):
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


async def test_get_statements(monkeypatch, db, user):
    # NON-dict return skips the DB-upsert cache branch.
    ret = []
    cap = _patch(monkeypatch, user, ret)

    result = await get_statements(99, user.id, db)

    assert cap["method"] == "problem.statements"
    assert cap["params"] == {"problemId": "99"}
    assert result is ret
