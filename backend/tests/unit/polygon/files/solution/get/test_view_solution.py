import api.user.polygon.files.solution.get.view_solution as mod
from api.user.polygon.files.solution.get.view_solution import view_solution


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


async def test_view_solution_dict_message(monkeypatch, db, user):
    cap = _patch(monkeypatch, user, {"message": "X"})

    result = await view_solution(7, "sol.cpp", user.id, db)

    assert cap["method"] == "problem.viewSolution"
    assert cap["params"] == {"problemId": "7", "name": "sol.cpp"}
    assert result == "X"


async def test_view_solution_non_dict(monkeypatch, db, user):
    _patch(monkeypatch, user, 123)

    result = await view_solution(7, "sol.cpp", user.id, db)

    assert result == str(123)
