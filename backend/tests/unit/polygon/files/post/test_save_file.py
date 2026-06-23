import api.user.polygon.files.post.save_file as mod
from api.user.polygon.files.post.save_file import save_file


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


async def test_save_file_base_str(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_file(5, "source", "gen.cpp", "int main(){}", user.id, db)
    assert cap["method"] == "problem.saveFile"
    assert cap["params"] == {
        "problemId": "5",
        "type": "source",
        "name": "gen.cpp",
        "file": "int main(){}",
    }


async def test_save_file_bytes_passthrough(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_file(5, "source", "gen.cpp", b"\x00\x01", user.id, db)
    assert cap["params"]["file"] == b"\x00\x01"


async def test_save_file_source_type_and_check_existing(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_file(
        5,
        "source",
        "gen.cpp",
        "x",
        user.id,
        db,
        source_type="cpp.g++17",
        check_existing=True,
    )
    assert cap["params"]["sourceType"] == "cpp.g++17"
    assert cap["params"]["checkExisting"] == "true"


async def test_save_file_resource_for_types(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_file(
        5,
        "resource",
        "olymp.sty",
        "x",
        user.id,
        db,
        for_types="cpp.*",
    )
    assert cap["params"]["forTypes"] == "cpp.*"
    assert cap["params"]["stages"] == ""
    assert cap["params"]["assets"] == ""


async def test_save_file_source_for_types_ignored(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_file(
        5,
        "source",
        "gen.cpp",
        "x",
        user.id,
        db,
        for_types="cpp.*",
    )
    assert "forTypes" not in cap["params"]
    assert "stages" not in cap["params"]
    assert "assets" not in cap["params"]
