import api.user.polygon.files.validator.post.set_validator as mod
from api.user.polygon.files.validator.post.set_validator import set_validator


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


async def test_set_validator_makes_two_calls(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await set_validator(5, "val.cpp", "code", user.id, db)
    assert cap["user_id"] == user.id
    calls = cap["calls"]
    assert len(calls) == 2
    assert calls[0] == (
        "problem.saveFile",
        {
            "problemId": "5",
            "type": "source",
            "name": "val.cpp",
            "file": "code",
        },
    )
    assert calls[1] == (
        "problem.setValidator",
        {"problemId": "5", "validator": "val.cpp"},
    )
