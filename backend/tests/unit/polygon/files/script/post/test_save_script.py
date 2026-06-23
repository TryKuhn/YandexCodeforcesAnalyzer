import api.user.polygon.files.script.post.save_script as mod
from api.user.polygon.files.script.post.save_script import save_script


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


async def test_save_script(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_script(5, "tests", "gen 1 > 1", user.id, db)
    assert cap["method"] == "problem.saveScript"
    assert cap["params"] == {
        "problemId": "5",
        "testset": "tests",
        "source": "gen 1 > 1",
    }
