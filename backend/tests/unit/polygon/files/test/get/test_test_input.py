import api.user.polygon.files.test.get.test_input as mod
from api.user.polygon.files.test.get.test_input import get_test_input


def _patch(monkeypatch, user, ret={"ok": True}):
    cap = {}

    async def fake_get_user(user_id, db):
        cap["user_id"] = user_id
        return user

    async def fake_polygon_call(method_name, params, u):
        cap.setdefault("calls", []).append((method_name, dict(params)))
        cap["method"] = method_name
        cap["params"] = params
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)
    return cap


async def test_get_test_input_params(monkeypatch, db, user):
    cap = _patch(monkeypatch, user, ret={"message": "HELLO"})
    await get_test_input(5, "tests", 3, user.id, db)
    assert cap["method"] == "problem.testInput"
    assert cap["params"] == {"problemId": "5", "testset": "tests", "testIndex": "3"}


async def test_get_test_input_message_extraction(monkeypatch, db, user):
    _patch(monkeypatch, user, ret={"message": "HELLO"})
    result = await get_test_input(5, "tests", 3, user.id, db)
    assert result == "HELLO"


async def test_get_test_input_non_dict(monkeypatch, db, user):
    _patch(monkeypatch, user, ret="RAW")
    result = await get_test_input(5, "tests", 3, user.id, db)
    assert result == "RAW"
