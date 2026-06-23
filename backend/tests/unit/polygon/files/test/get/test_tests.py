import api.user.polygon.files.test.get.tests as mod
from api.user.polygon.files.test.get.tests import get_tests


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


async def test_get_tests_base(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await get_tests(5, "tests", user.id, db)
    assert cap["method"] == "problem.tests"
    assert cap["params"] == {"problemId": "5", "testset": "tests"}
    assert "noInputs" not in cap["params"]


async def test_get_tests_no_inputs(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await get_tests(5, "tests", user.id, db, no_inputs=True)
    assert cap["params"]["noInputs"] == "true"
