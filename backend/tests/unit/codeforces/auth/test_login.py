"""Unit tests for api/user/codeforces/auth/login.py — link_codeforces handler."""
import pytest
from fastapi import HTTPException

import api.user.codeforces.auth.login as login_mod
from api.pydantic_schemas import LinkCodeforces
from api.user.codeforces.auth.login import link_codeforces


class _FakeClientSession:
    """Stand-in for aiohttp.ClientSession used as an async context manager."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_link_success_persists_credentials(db, user, monkeypatch):
    monkeypatch.setattr(login_mod, "ClientSession", lambda: _FakeClientSession())

    async def fake_get_response(client, url, params):
        return []  # CF user.friends OK

    monkeypatch.setattr(login_mod, "get_response", fake_get_response)

    payload = LinkCodeforces(api_key="K", api_secret="S")
    result = await link_codeforces(payload, user_id=user.id, db=db)

    assert result == {"message": "Codeforces account successfully linked"}
    await db.refresh(user)
    assert user.codeforces_api_key == "K"
    assert user.codeforces_api_secret == "S"


@pytest.mark.asyncio
async def test_link_user_not_found_raises_404(db, monkeypatch):
    monkeypatch.setattr(login_mod, "ClientSession", lambda: _FakeClientSession())
    payload = LinkCodeforces(api_key="K", api_secret="S")
    with pytest.raises(HTTPException) as exc:
        await link_codeforces(payload, user_id=999999, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_link_invalid_credentials_raises_400(db, user, monkeypatch):
    monkeypatch.setattr(login_mod, "ClientSession", lambda: _FakeClientSession())

    async def fake_get_response(client, url, params):
        raise HTTPException(status_code=400, detail="apiKey invalid")

    monkeypatch.setattr(login_mod, "get_response", fake_get_response)

    payload = LinkCodeforces(api_key="bad", api_secret="bad")
    with pytest.raises(HTTPException) as exc:
        await link_codeforces(payload, user_id=user.id, db=db)
    assert exc.value.status_code == 400
    assert "Invalid Codeforces credentials" in exc.value.detail


@pytest.mark.asyncio
async def test_link_network_error_raises_502(db, user, monkeypatch):
    monkeypatch.setattr(login_mod, "ClientSession", lambda: _FakeClientSession())

    async def fake_get_response(client, url, params):
        raise ConnectionError("boom")

    monkeypatch.setattr(login_mod, "get_response", fake_get_response)

    payload = LinkCodeforces(api_key="K", api_secret="S")
    with pytest.raises(HTTPException) as exc:
        await link_codeforces(payload, user_id=user.id, db=db)
    assert exc.value.status_code == 502
