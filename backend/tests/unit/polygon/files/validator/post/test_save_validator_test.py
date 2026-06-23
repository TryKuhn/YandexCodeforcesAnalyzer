import api.user.polygon.files.validator.post.save_validator_test as mod
from api.user.polygon.files.validator.post.save_validator_test import (
    save_validator_test,
)


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


async def test_save_validator_test_base_params(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_validator_test(5, 3, "in", "OK", user.id, db)
    assert cap["method"] == "problem.saveValidatorTest"
    assert cap["params"] == {
        "problemId": "5",
        "testIndex": "3",
        "testInput": "in",
        "testVerdict": "OK",
    }
    assert "checkExisting" not in cap["params"]
    assert "testGroup" not in cap["params"]
    assert "testset" not in cap["params"]
    assert cap["user_id"] == user.id


async def test_save_validator_test_all_optionals(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_validator_test(
        5,
        3,
        "in",
        "OK",
        user.id,
        db,
        check_existing=True,
        test_group="g1",
        testset="tests",
    )
    assert cap["params"]["checkExisting"] == "true"
    assert cap["params"]["testGroup"] == "g1"
    assert cap["params"]["testset"] == "tests"
