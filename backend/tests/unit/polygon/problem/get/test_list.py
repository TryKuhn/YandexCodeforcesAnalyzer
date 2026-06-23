import api.user.polygon.problem.get.list as mod
from api.user.polygon.problem.get.list import list_problems


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


async def test_list_problems_defaults(monkeypatch, db, user):
    # Empty list => the for-loop body never runs, db.commit() is a no-op.
    cap = _patch(monkeypatch, user, ret=[])
    result = await list_problems(user.id, db)

    assert cap["method"] == "problems.list"
    assert cap["params"] == {}
    assert cap["user_id"] == user.id
    assert result == []


async def test_list_problems_all_filters(monkeypatch, db, user):
    cap = _patch(monkeypatch, user, ret=[])
    result = await list_problems(
        user.id, db, show_deleted=True, problem_id=7, name="A", owner="me"
    )

    assert cap["method"] == "problems.list"
    assert cap["params"] == {
        "showDeleted": "true",
        "id": "7",
        "name": "A",
        "owner": "me",
    }
    assert result == []
