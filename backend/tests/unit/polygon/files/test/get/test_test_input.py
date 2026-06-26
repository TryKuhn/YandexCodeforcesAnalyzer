import api.user.polygon.files.test.get.test_input as mod
from api.user.polygon.files.test.get.test_input import get_test_input


def _patch(monkeypatch, user, ret=None):
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


async def test_get_test_input_uses_problem_tests(monkeypatch, db, user):
    # Must use problem.tests (works for manual sample tests), NOT problem.testInput
    # (which only serves generated tests and returns plain text).
    cap = _patch(monkeypatch, user, ret=[{"index": 3, "input": "HELLO"}])
    result = await get_test_input(5, "tests", 3, user.id, db)
    assert cap["method"] == "problem.tests"
    assert cap["params"] == {"problemId": "5", "testset": "tests"}
    assert result == "HELLO"


async def test_get_test_input_picks_matching_index(monkeypatch, db, user):
    _patch(monkeypatch, user, ret=[
        {"index": 1, "input": "one"},
        {"index": 3, "input": "three"},
    ])
    assert await get_test_input(5, "tests", 3, user.id, db) == "three"


async def test_get_test_input_decodes_base64(monkeypatch, db, user):
    # manual test with binary-safe input only in inputBase64
    _patch(monkeypatch, user, ret=[{"index": 3, "inputBase64": "SEVMTE8="}])
    assert await get_test_input(5, "tests", 3, user.id, db) == "HELLO"


async def test_get_test_input_missing_returns_empty(monkeypatch, db, user):
    _patch(monkeypatch, user, ret=[{"index": 1, "input": "one"}])
    assert await get_test_input(5, "tests", 9, user.id, db) == ""
