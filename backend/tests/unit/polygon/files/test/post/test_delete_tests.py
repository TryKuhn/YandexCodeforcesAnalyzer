import api.user.polygon.files.test.post.delete_tests as mod
from api.user.polygon.files.test.post.delete_tests import delete_tests


def _patch(monkeypatch, user):
    cap = {}

    async def fake_get_user(user_id, db):
        return user

    async def fake_polygon_call(method_name, params, u):
        cap["method"] = method_name
        cap["params"] = params
        return None

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)
    return cap


async def test_delete_tests_sends_comma_separated_indices(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await delete_tests(5, "tests", [2, 3], user.id, db)
    assert cap["method"] == "problem.deleteTest"
    assert cap["params"] == {"problemId": "5", "testset": "tests", "testIndices": "2,3"}
