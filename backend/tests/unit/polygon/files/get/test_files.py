import api.user.polygon.files.get.files as mod
from api.user.polygon.files.get.files import get_files


def _patch(monkeypatch, user, ret={"ok": True}):
    cap = {}

    async def fake_get_user(user_id, db):
        cap["user_id"] = user_id
        return user

    async def fake_polygon_call(method_name, params, u):
        cap.setdefault("calls", []).append((method_name, dict(params)))
        cap["method"] = method_name
        cap["params"] = params
        cap["user"] = u
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)
    return cap


async def test_get_files(monkeypatch, db, user):
    cap = _patch(monkeypatch, user, ret={"ok": True})
    result = await get_files(5, user.id, db)
    assert cap["user_id"] == user.id
    assert cap["method"] == "problem.files"
    assert cap["params"] == {"problemId": "5"}
    assert result == {"ok": True}
