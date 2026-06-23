import api.user.polygon.problem.settings.save_test_group as mod
from api.user.polygon.problem.settings.save_test_group import save_test_group


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


async def test_save_test_group_base(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    result = await save_test_group(42, "tests", "1", 50, user.id, db)

    assert cap["method"] == "problem.saveTestGroup"
    assert cap["params"] == {
        "problemId": "42",
        "testset": "tests",
        "group": "1",
        "points": "50",
    }
    assert result == {"ok": True}


async def test_save_test_group_all_options(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    result = await save_test_group(
        42,
        "tests",
        "1",
        50,
        user.id,
        db,
        points_policy="COMPLETE_GROUP",
        feedback_policy="NONE",
        dependencies=[1, 2, 3],
    )

    assert cap["params"] == {
        "problemId": "42",
        "testset": "tests",
        "group": "1",
        "points": "50",
        "pointsPolicy": "COMPLETE_GROUP",
        "feedbackPolicy": "NONE",
        "dependencies": "1,2,3",
    }
    assert result == {"ok": True}
