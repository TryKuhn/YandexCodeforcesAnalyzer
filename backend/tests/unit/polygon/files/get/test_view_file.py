import api.user.polygon.files.get.view_file as mod
from api.user.polygon.files.get.view_file import view_file


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


async def test_view_file_params(monkeypatch, db, user):
    cap = _patch(monkeypatch, user, ret={"message": "HELLO"})
    await view_file(5, "source", "gen.cpp", user.id, db)
    assert cap["method"] == "problem.viewFile"
    assert cap["params"] == {"problemId": "5", "type": "source", "name": "gen.cpp"}


async def test_view_file_message_extraction(monkeypatch, db, user):
    _patch(monkeypatch, user, ret={"message": "HELLO"})
    result = await view_file(5, "source", "gen.cpp", user.id, db)
    assert result == "HELLO"


async def test_view_file_non_dict(monkeypatch, db, user):
    _patch(monkeypatch, user, ret="RAW")
    result = await view_file(5, "source", "gen.cpp", user.id, db)
    assert result == "RAW"
