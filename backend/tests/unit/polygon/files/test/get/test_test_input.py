import api.user.polygon.files.test.get.test_input as mod
from api.user.polygon.files.test.get.test_input import get_test_input


def _patch(monkeypatch, user, ret=None):
    cap = {}

    async def fake_get_user(user_id, db):
        return user

    async def fake_polygon_call(method_name, params, u):
        cap["method"] = method_name
        cap["params"] = params
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)
    return cap


async def test_get_test_input_uses_test_input_method(monkeypatch, db, user):
    # problem.testInput works for manual AND generated tests; get_response wraps
    # the plain-text body as {"message": ...}.
    cap = _patch(monkeypatch, user, ret={"message": "1 5"})
    assert await get_test_input(5, "tests", 3, user.id, db) == "1 5"
    assert cap["method"] == "problem.testInput"
    assert cap["params"] == {"problemId": "5", "testset": "tests", "testIndex": "3"}


async def test_get_test_input_non_dict_stringified(monkeypatch, db, user):
    _patch(monkeypatch, user, ret="raw text")
    assert await get_test_input(5, "tests", 3, user.id, db) == "raw text"


async def test_get_test_input_empty_when_no_message(monkeypatch, db, user):
    _patch(monkeypatch, user, ret={})
    assert await get_test_input(5, "tests", 3, user.id, db) == ""
