import api.user.polygon.files.checker.post.save_checker_test as mod
from api.user.polygon.files.checker.post.save_checker_test import save_checker_test


def _patch(monkeypatch, user):
    captured = {}

    async def fake_get_user(user_id, db):
        captured["user_id"] = user_id
        return user

    async def fake_polygon_call(method_name, params, u):
        captured.setdefault("calls", []).append((method_name, params))
        captured["method"] = method_name
        captured["params"] = params
        return {"ok": True}

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)
    return captured


async def test_save_checker_test_base_params(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_checker_test(5, 3, "in", "out", "ans", "OK", user.id, db)
    assert cap["method"] == "problem.saveCheckerTest"
    assert cap["params"] == {
        "problemId": "5",
        "testIndex": "3",
        "testInput": "in",
        "testOutput": "out",
        "testAnswer": "ans",
        "testVerdict": "OK",
    }
    assert "checkExisting" not in cap["params"]
    assert cap["user_id"] == user.id


async def test_save_checker_test_check_existing_true(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_checker_test(
        5, 3, "in", "out", "ans", "OK", user.id, db, check_existing=True
    )
    assert cap["params"]["checkExisting"] == "true"


async def test_save_checker_test_check_existing_false(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_checker_test(
        5, 3, "in", "out", "ans", "OK", user.id, db, check_existing=False
    )
    assert cap["params"]["checkExisting"] == "false"
