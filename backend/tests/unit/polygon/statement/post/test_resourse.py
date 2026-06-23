import api.user.polygon.statement.post.resourse as mod
from api.user.polygon.statement.post.resourse import save_statement_resource


def _patch(monkeypatch, user, ret={"ok": True}):
    cap = {}

    async def fake_get_user(user_id, db):
        cap["user_id"] = user_id
        return user

    async def fake_polygon_call(method_name, params, u):
        cap["method"] = method_name
        cap["params"] = params
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)
    return cap


async def test_save_statement_resource_base(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    content = b"raw bytes"

    await save_statement_resource(4, "olymp.sty", content, user.id, db)

    assert cap["method"] == "problem.saveStatementResource"
    params = cap["params"]
    assert params == {
        "problemId": "4",
        "name": "olymp.sty",
        "file": content,
    }
    assert params["file"] is content
    assert "checkExisting" not in params


async def test_save_statement_resource_check_existing_false(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)

    await save_statement_resource(
        4, "olymp.sty", b"x", user.id, db, check_existing=False
    )

    assert cap["params"]["checkExisting"] == "false"
