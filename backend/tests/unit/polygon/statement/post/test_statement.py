import api.user.polygon.statement.post.statement as mod
from api.user.polygon.statement.post.statement import save_statement


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


async def test_save_statement_base_only(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)

    await save_statement(
        1, "russian", "Name", "Legend", "In", "Out", user.id, db
    )

    assert cap["method"] == "problem.saveStatement"
    params = cap["params"]
    assert params == {
        "problemId": "1",
        "lang": "russian",
        "encoding": "utf-8",
        "name": "Name",
        "legend": "Legend",
        "input": "In",
        "output": "Out",
    }
    assert "scoring" not in params
    assert "interaction" not in params
    assert "notes" not in params
    assert "tutorial" not in params


async def test_save_statement_all_optionals(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)

    await save_statement(
        1,
        "russian",
        "Name",
        "Legend",
        "In",
        "Out",
        user.id,
        db,
        scoring="S",
        interaction="I",
        notes="N",
        tutorial="T",
        encoding="windows-1251",
    )

    params = cap["params"]
    assert params["encoding"] == "windows-1251"
    assert params["scoring"] == "S"
    assert params["interaction"] == "I"
    assert params["notes"] == "N"
    assert params["tutorial"] == "T"
