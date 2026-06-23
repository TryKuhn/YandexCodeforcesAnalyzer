import api.user.polygon.files.interactor.post.set_interactor as mod
from api.user.polygon.files.interactor.post.set_interactor import set_interactor


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


async def test_set_interactor_two_calls(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await set_interactor(5, "interactor.cpp", "int main(){}", user.id, db)
    calls = cap["calls"]
    assert len(calls) == 2
    assert calls[0] == (
        "problem.saveFile",
        {
            "problemId": "5",
            "type": "source",
            "name": "interactor.cpp",
            "file": "int main(){}",
        },
    )
    assert calls[1] == (
        "problem.setInteractor",
        {"problemId": "5", "interactor": "interactor.cpp"},
    )
