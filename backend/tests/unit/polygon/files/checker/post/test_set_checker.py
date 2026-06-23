import api.user.polygon.files.checker.post.set_checker as mod
from api.user.polygon.files.checker.post.set_checker import set_checker


def _patch(monkeypatch, user):
    captured = {}

    async def fake_get_user(user_id, db):
        captured["user_id"] = user_id
        return user

    async def fake_polygon_call(method_name, params, u):
        captured.setdefault("calls", []).append((method_name, params))
        captured["method"] = method_name
        captured["params"] = params
        return {"ok": True}

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)
    return captured


async def test_set_checker_makes_two_calls(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await set_checker(5, "check.cpp", "code", user.id, db)
    assert cap["user_id"] == user.id
    calls = cap["calls"]
    assert len(calls) == 2
    assert calls[0] == (
        "problem.saveFile",
        {
            "problemId": "5",
            "type": "source",
            "name": "check.cpp",
            "file": "code",
        },
    )
    assert calls[1] == (
        "problem.setChecker",
        {"problemId": "5", "checker": "check.cpp"},
    )
