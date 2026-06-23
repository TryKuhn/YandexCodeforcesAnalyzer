import api.user.polygon.problem.get.info as mod
from api.user.polygon.problem.get.info import get_problem_info


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


async def test_get_problem_info_skips_cache_for_non_dict(monkeypatch, db, user):
    # Return a non-dict so the `if isinstance(info, dict)` cache branch is skipped.
    cap = _patch(monkeypatch, user, ret=["x"])
    result = await get_problem_info(42, user.id, db)

    assert cap["method"] == "problem.info"
    assert cap["params"] == {"problemId": "42"}
    assert cap["user_id"] == user.id
    assert cap["user"] is user
    assert result == ["x"]
