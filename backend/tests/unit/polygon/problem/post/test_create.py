import api.user.polygon.problem.post.create as mod
from api.user.polygon.problem.post.create import create_problem


def _patch(monkeypatch, user, ret):
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


async def test_create_problem_dict_result(monkeypatch, db, user):
    cap = _patch(monkeypatch, user, ret={"id": 123})
    result = await create_problem("My Problem", user.id, db)

    assert cap["method"] == "problem.create"
    assert cap["params"] == {"name": "My Problem"}
    assert cap["user"] is user
    assert result == 123


async def test_create_problem_non_dict_result(monkeypatch, db, user):
    cap = _patch(monkeypatch, user, ret=99)
    result = await create_problem("My Problem", user.id, db)

    assert cap["method"] == "problem.create"
    assert cap["params"] == {"name": "My Problem"}
    assert result == 99
