import api.user.polygon.files.generator.post.save_file as mod
from api.user.polygon.files.generator.post.save_file import set_generator


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


async def test_set_generator_base(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await set_generator(5, "gen.cpp", "int main(){}", user.id, db)
    assert cap["method"] == "problem.saveFile"
    assert cap["params"] == {
        "problemId": "5",
        "type": "source",
        "name": "gen.cpp",
        "file": "int main(){}",
    }
    assert "sourceType" not in cap["params"]


async def test_set_generator_with_source_type(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await set_generator(5, "gen.cpp", "x", user.id, db, source_type="cpp.g++17")
    assert cap["params"]["sourceType"] == "cpp.g++17"
