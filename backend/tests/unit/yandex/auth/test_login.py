"""Unit tests for api/user/yandex/auth/login.py — auth_url + callback handlers."""
import httpx
import pytest
from fastapi import HTTPException

import api.user.yandex.auth.login as login_mod
from api.user.yandex.auth.login import (YandexCallbackRequest,
                                        get_yandex_auth_url, yandex_callback)


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


def _fake_client_factory(*, response=None, raise_exc=None):
    """Build a stand-in for httpx.AsyncClient() usable as an async ctx manager."""
    captured = {}

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, data=None):
            captured["url"] = url
            captured["data"] = data
            if raise_exc is not None:
                raise raise_exc
            return response

    return _FakeClient, captured


# --------------------------------------------------------------------------- #
# auth_url
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_auth_url_contains_client_id(monkeypatch):
    monkeypatch.setattr(login_mod.settings, "YANDEX_CLIENT_ID", "my-client-id")
    result = await get_yandex_auth_url()
    assert "url" in result
    assert "response_type=code" in result["url"]
    assert "client_id=my-client-id" in result["url"]


# --------------------------------------------------------------------------- #
# callback
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_callback_success_stores_token(db, user, monkeypatch):
    fake_cls, captured = _fake_client_factory(
        response=_FakeResponse(200, {"access_token": "new-token"})
    )
    monkeypatch.setattr(login_mod.httpx, "AsyncClient", lambda: fake_cls())

    result = await yandex_callback(
        YandexCallbackRequest(code="abc"), user_id=user.id, db=db
    )

    assert result == {"message": "Yandex account successfully linked"}
    await db.refresh(user)
    assert user.yandex_access_token == "new-token"
    # OAuth request carried the auth code
    assert captured["data"]["code"] == "abc"
    assert captured["data"]["grant_type"] == "authorization_code"


@pytest.mark.asyncio
async def test_callback_network_error_raises_502(db, user, monkeypatch):
    fake_cls, _ = _fake_client_factory(raise_exc=httpx.RequestError("boom"))
    monkeypatch.setattr(login_mod.httpx, "AsyncClient", lambda: fake_cls())

    with pytest.raises(HTTPException) as exc:
        await yandex_callback(
            YandexCallbackRequest(code="abc"), user_id=user.id, db=db
        )
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_callback_non_200_raises_400(db, user, monkeypatch):
    fake_cls, _ = _fake_client_factory(
        response=_FakeResponse(403, {}, text="forbidden")
    )
    monkeypatch.setattr(login_mod.httpx, "AsyncClient", lambda: fake_cls())

    with pytest.raises(HTTPException) as exc:
        await yandex_callback(
            YandexCallbackRequest(code="abc"), user_id=user.id, db=db
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_callback_user_not_found_raises_404(db, monkeypatch):
    fake_cls, _ = _fake_client_factory(
        response=_FakeResponse(200, {"access_token": "tok"})
    )
    monkeypatch.setattr(login_mod.httpx, "AsyncClient", lambda: fake_cls())

    with pytest.raises(HTTPException) as exc:
        await yandex_callback(
            YandexCallbackRequest(code="abc"), user_id=999999, db=db
        )
    assert exc.value.status_code == 404
