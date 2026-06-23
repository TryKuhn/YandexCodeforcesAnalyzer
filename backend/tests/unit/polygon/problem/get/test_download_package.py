import api.user.polygon.problem.get.download_package as mod
from api.user.polygon.problem.get.download_package import download_package


def _patch(monkeypatch, user, ret=b"ZIP"):
    cap = {}

    async def fake_get_user(user_id, db):
        cap["user_id"] = user_id
        return user

    async def fake_polygon_call_binary(method_name, params, u):
        cap["method"] = method_name
        cap["params"] = params
        cap["user"] = u
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call_binary", fake_polygon_call_binary)
    return cap


async def test_download_package_without_type(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    result = await download_package(42, 9, user.id, db)

    assert cap["method"] == "problem.package"
    assert cap["params"] == {"problemId": "42", "packageId": "9"}
    assert "type" not in cap["params"]
    assert cap["user"] is user
    assert result == b"ZIP"


async def test_download_package_with_type(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    result = await download_package(42, 9, user.id, db, package_type="windows")

    assert cap["method"] == "problem.package"
    assert cap["params"] == {
        "problemId": "42",
        "packageId": "9",
        "type": "windows",
    }
    assert result == b"ZIP"
