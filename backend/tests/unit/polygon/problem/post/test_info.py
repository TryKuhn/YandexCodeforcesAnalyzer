import api.user.polygon.problem.post.info as mod
from api.user.polygon.problem.post.info import update_info


def _patch(monkeypatch, user, ret={"ok": True}):
    cap = {}

    async def fake_get_user(user_id, db):
        cap["user_id"] = user_id
        return user

    async def fake_polygon_call(method_name, params, u):
        cap["method"] = method_name
        cap["params"] = params
        cap["user"] = u
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)
    return cap


async def test_update_info_defaults(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    result = await update_info(42, user.id, db)

    assert cap["method"] == "problem.updateInfo"
    assert cap["params"] == {"problemId": "42"}
    assert cap["user"] is user
    assert result == {"ok": True}


async def test_update_info_all_set(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    result = await update_info(
        42,
        user.id,
        db,
        input_file="in.txt",
        output_file="out.txt",
        interactive=True,
        well_formed=False,
        time_limit=1000,
        memory_limit=256,
    )

    assert cap["params"] == {
        "problemId": "42",
        "inputFile": "in.txt",
        "outputFile": "out.txt",
        "interactive": "true",
        "wellFormed": "false",
        "timeLimit": "1000",
        "memoryLimit": "256",
    }
    assert result == {"ok": True}
