import api.user.polygon.problem.post.package as mod
from api.user.polygon.problem.post.package import build_package


class _Ctx:
    def __init__(self, v):
        self._v = v

    async def __aenter__(self):
        return self._v

    async def __aexit__(self, *a):
        return False


def _patch(monkeypatch):
    cap = {}

    monkeypatch.setattr(mod, "create_signature", lambda *a, **k: "SIG")

    async def fake_get_response(session, url, params):
        cap["url"] = url
        cap["params"] = dict(params)
        return None

    monkeypatch.setattr(mod, "get_response", fake_get_response)
    monkeypatch.setattr(mod, "ClientSession", lambda *a, **k: _Ctx(object()))
    return cap


async def test_build_package(monkeypatch, db, user):
    # `user` fixture is persisted in `db`; build_package reads it via its own select.
    cap = _patch(monkeypatch)
    result = await build_package(555, user.id, db)

    assert result == {"detail": "Пакет отправлен на сборку"}
    assert cap["params"]["apiKey"] == "key"
    assert cap["params"]["problemId"] == "555"
    assert cap["params"]["full"] == "true"
    assert cap["params"]["verify"] == "true"
    assert cap["params"]["apiSig"] == "SIG"
