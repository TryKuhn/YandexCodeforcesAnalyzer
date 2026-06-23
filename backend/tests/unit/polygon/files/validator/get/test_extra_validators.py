import api.user.polygon.files.validator.get.extra_validators as mod
from api.user.polygon.files.validator.get.extra_validators import get_extra_validators


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


async def test_get_extra_validators_calls_method(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await get_extra_validators(5, user.id, db)
    assert cap["method"] == "problem.extraValidators"
    assert cap["params"] == {"problemId": "5"}
    assert cap["user_id"] == user.id
