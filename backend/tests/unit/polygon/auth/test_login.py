"""Unit tests for api/user/polygon/auth/login.py route handler."""
import pytest
from fastapi import HTTPException

import api.user.polygon.auth.login as mod
from api.pydantic_schemas import LinkCodeforces
from api.user.polygon.auth.login import link_polygon
from api.user.polygon.client import PolygonAPIError


def _patch_request(monkeypatch, effect):
    calls = []

    async def fake_request(method, params, *, api_key, api_secret, **kw):
        calls.append((method, dict(params), api_key, api_secret))
        if isinstance(effect, Exception):
            raise effect
        return effect

    monkeypatch.setattr(mod, "request", fake_request)
    return calls


async def test_link_polygon_success(monkeypatch, db, user):
    calls = _patch_request(monkeypatch, [])

    payload = LinkCodeforces(api_key="newkey", api_secret="newsecret")
    result = await link_polygon(payload=payload, user_id=user.id, db=db)
    assert result == {"message": "Polygon account successfully linked"}
    # Probe is signed with the NEW credentials, not the stored ones.
    assert calls == [("problems.list", {}, "newkey", "newsecret")]

    await db.refresh(user)
    assert user.polygon_api_key == "newkey"
    assert user.polygon_api_secret == "newsecret"


async def test_link_polygon_user_not_found(monkeypatch, db, user):
    payload = LinkCodeforces(api_key="k", api_secret="s")
    with pytest.raises(HTTPException) as exc:
        await link_polygon(payload=payload, user_id=999999, db=db)
    assert exc.value.status_code == 404


async def test_link_polygon_invalid_credentials(monkeypatch, db, user):
    _patch_request(monkeypatch, PolygonAPIError("apiKey: Incorrect signature", http_status=400))

    payload = LinkCodeforces(api_key="k", api_secret="s")
    with pytest.raises(HTTPException) as exc:
        await link_polygon(payload=payload, user_id=user.id, db=db)
    assert exc.value.status_code == 400
    assert "Invalid Polygon credentials" in exc.value.detail
    await db.refresh(user)
    assert user.polygon_api_key == "key"  # unchanged


async def test_link_polygon_unreachable_is_502(monkeypatch, db, user):
    _patch_request(monkeypatch, PolygonAPIError("Polygon недоступен", http_status=502))

    payload = LinkCodeforces(api_key="k", api_secret="s")
    with pytest.raises(HTTPException) as exc:
        await link_polygon(payload=payload, user_id=user.id, db=db)
    assert exc.value.status_code == 502
