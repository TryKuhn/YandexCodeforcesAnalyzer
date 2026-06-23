"""Unit tests for api/user/polygon/auth/login.py route handler."""
import pytest
from fastapi import HTTPException

import api.user.polygon.auth.login as mod
from api.pydantic_schemas import LinkCodeforces
from api.user.polygon.auth.login import link_polygon
from api.user.polygon.get_response import PolygonAPIError


class _FakeClientSession:
    """Async context manager stand-in for aiohttp.ClientSession."""
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _patch_session(monkeypatch):
    monkeypatch.setattr(mod, "ClientSession", lambda *a, **k: _FakeClientSession())


@pytest.mark.asyncio
async def test_link_polygon_success(monkeypatch, db, user):
    _patch_session(monkeypatch)

    async def fake_get_response(session, url, params):
        return []

    monkeypatch.setattr(mod, "get_response", fake_get_response)

    payload = LinkCodeforces(api_key="newkey", api_secret="newsecret")
    result = await link_polygon(payload=payload, user_id=user.id, db=db)
    assert result == {"message": "Polygon account successfully linked"}

    await db.refresh(user)
    assert user.polygon_api_key == "newkey"
    assert user.polygon_api_secret == "newsecret"


@pytest.mark.asyncio
async def test_link_polygon_user_not_found(monkeypatch, db, user):
    payload = LinkCodeforces(api_key="k", api_secret="s")
    with pytest.raises(HTTPException) as exc:
        await link_polygon(payload=payload, user_id=999999, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_link_polygon_invalid_credentials(monkeypatch, db, user):
    _patch_session(monkeypatch)

    async def fake_get_response(session, url, params):
        raise PolygonAPIError("bad creds")

    monkeypatch.setattr(mod, "get_response", fake_get_response)

    payload = LinkCodeforces(api_key="k", api_secret="s")
    with pytest.raises(HTTPException) as exc:
        await link_polygon(payload=payload, user_id=user.id, db=db)
    assert exc.value.status_code == 400
    assert "Invalid Polygon credentials" in exc.value.detail


@pytest.mark.asyncio
async def test_link_polygon_network_error(monkeypatch, db, user):
    _patch_session(monkeypatch)

    async def fake_get_response(session, url, params):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(mod, "get_response", fake_get_response)

    payload = LinkCodeforces(api_key="k", api_secret="s")
    with pytest.raises(HTTPException) as exc:
        await link_polygon(payload=payload, user_id=user.id, db=db)
    assert exc.value.status_code == 502
