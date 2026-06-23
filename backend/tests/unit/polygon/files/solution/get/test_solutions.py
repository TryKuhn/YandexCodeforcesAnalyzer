import api.user.polygon.files.solution.get.solutions as mod
from api.user.polygon.files.solution.get.solutions import get_solutions


def _patch(monkeypatch, user, ret={"x": 1}):
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


async def test_get_solutions(monkeypatch, db, user):
    # NON-list return skips the DB-upsert cache branch.
    ret = {"x": 1}
    cap = _patch(monkeypatch, user, ret)

    result = await get_solutions(42, user.id, db)

    assert cap["method"] == "problem.solutions"
    assert cap["params"] == {"problemId": "42"}
    assert result is ret
