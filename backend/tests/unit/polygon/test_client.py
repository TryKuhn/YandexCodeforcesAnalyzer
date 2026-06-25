"""Unit tests for api.user.polygon.client (get_user / polygon_call / polygon_call_binary).

We monkeypatch the module-level ``create_signature``, ``get_response`` and
``ClientSession`` so no network or real crypto runs, and so we can assert
exactly which params the client builds and passes downstream.
"""
import pytest
from fastapi import HTTPException

import api.user.polygon.client as client_mod
from api.user.polygon.client import (get_user, polygon_call,
                                      polygon_call_binary)


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------
class _FakeSessionCtx:
    """async-context-manager returned by ClientSession()."""

    def __init__(self, recorder):
        self._recorder = recorder

    async def __aenter__(self):
        return self._recorder

    async def __aexit__(self, *exc):
        return False


class _FakePostCtx:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class _FakeBinaryResponse:
    def __init__(self, body: bytes, status: int):
        self._body = body
        self.status = status

    async def read(self):
        return self._body

    async def text(self):
        return self._body.decode("utf-8", errors="replace")


class _FakeClientForBinary:
    """ClientSession() used by polygon_call_binary: records post(url, data=)."""

    def __init__(self, response):
        self._response = response
        self.posted = []

    def post(self, url, data=None):
        self.posted.append((url, data))
        return _FakePostCtx(self._response)


# --------------------------------------------------------------------------
# get_user
# --------------------------------------------------------------------------
async def test_get_user_returns_user(db, user):
    got = await get_user(user.id, db)
    assert got.id == user.id
    assert got.polygon_api_key == "key"


async def test_get_user_missing_user_raises_401(db):
    with pytest.raises(HTTPException) as exc:
        await get_user(999999, db)
    assert exc.value.status_code == 401


async def test_get_user_no_polygon_key_raises_401(db, user):
    user.polygon_api_key = None
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await get_user(user.id, db)
    assert exc.value.status_code == 401
    assert "not configured" in exc.value.detail


# --------------------------------------------------------------------------
# polygon_call
# --------------------------------------------------------------------------
@pytest.fixture
def patched_call(monkeypatch):
    """Patch create_signature + get_response + ClientSession in the client module.

    Returns a dict that captures: the sig args, the data passed to get_response.
    """
    captured = {}

    def fake_create_signature(method_name, params, secret):
        captured["sig_method"] = method_name
        captured["sig_params"] = dict(params)
        captured["sig_secret"] = secret
        return "SIGVALUE"

    async def fake_get_response(client, url, params):
        captured["url"] = str(url)
        captured["data"] = params
        return {"ok": True}

    monkeypatch.setattr(client_mod, "create_signature", fake_create_signature)
    monkeypatch.setattr(client_mod, "get_response", fake_get_response)
    # ClientSession() context manager -> a dummy client (unused by fake_get_response).
    monkeypatch.setattr(client_mod, "ClientSession", lambda *a, **k: _FakeSessionCtx(object()))
    monkeypatch.setattr(client_mod, "time", lambda: 1700000000.0)
    return captured


async def test_polygon_call_builds_auth_params_and_signs(patched_call, user):
    result = await polygon_call("problem.info", {"problemId": "5"}, user)
    assert result == {"ok": True}

    # Signature computed over apiKey/time/text params (no apiSig yet).
    sp = patched_call["sig_params"]
    assert sp["apiKey"] == "key"
    assert sp["time"] == "1700000000"
    assert sp["problemId"] == "5"
    assert "apiSig" not in sp
    assert patched_call["sig_method"] == "problem.info"
    assert patched_call["sig_secret"] == "secret"


async def test_polygon_call_includes_apisig_in_request_data(patched_call, user):
    await polygon_call("problem.info", {"problemId": "5"}, user)
    data = patched_call["data"]
    assert data["apiSig"] == "SIGVALUE"
    assert data["apiKey"] == "key"
    assert data["problemId"] == "5"


async def test_polygon_call_url_is_host_slash_method(patched_call, user):
    await polygon_call("problem.tests", {}, user)
    assert patched_call["url"].endswith("/problem.tests")


async def test_polygon_call_coerces_non_str_text_params(patched_call, user):
    await polygon_call("m", {"problemId": 5, "flag": True}, user)
    sp = patched_call["sig_params"]
    assert sp["problemId"] == "5"
    assert sp["flag"] == "True"


async def test_polygon_call_signs_utf8_bytes_as_text(patched_call, user):
    # Text passed as bytes (valid UTF-8) must be DECODED and SIGNED — Polygon
    # signs content params, so excluding it would cause 'Incorrect signature'.
    await polygon_call("problem.saveTest", {"problemId": "5", "testInput": b"5 6 7"}, user)
    assert patched_call["sig_params"]["testInput"] == "5 6 7"
    assert patched_call["data"]["testInput"] == "5 6 7"


async def test_polygon_call_excludes_non_utf8_binary_from_signature(patched_call, user):
    # Only genuine binary (not valid UTF-8, e.g. an image) is excluded from the
    # signature and sent as a raw multipart field.
    content = b"\xff\xfe\x00binary"
    await polygon_call(
        "problem.saveStatementResource", {"problemId": "5", "file": content}, user
    )
    assert "file" not in patched_call["sig_params"]
    assert patched_call["data"]["file"] == content
    assert isinstance(patched_call["data"]["file"], bytes)


# --------------------------------------------------------------------------
# polygon_call_binary
# --------------------------------------------------------------------------
async def test_polygon_call_binary_returns_bytes(monkeypatch, user):
    fake_client = _FakeClientForBinary(_FakeBinaryResponse(b"ZIPDATA", 200))
    monkeypatch.setattr(client_mod, "ClientSession", lambda *a, **k: _FakeSessionCtx(fake_client))
    monkeypatch.setattr(client_mod, "create_signature", lambda *a, **k: "SIG")
    monkeypatch.setattr(client_mod, "time", lambda: 1700000000.0)

    out = await polygon_call_binary("problem.package", {"packageId": 9}, user)
    assert out == b"ZIPDATA"

    url, data = fake_client.posted[0]
    assert str(url).endswith("/problem.package")
    assert data["apiKey"] == "key"
    assert data["time"] == "1700000000"
    assert data["packageId"] == "9"  # coerced to str
    assert data["apiSig"] == "SIG"


async def test_polygon_call_binary_non_200_raises(monkeypatch, user):
    from api.user.polygon.get_response import PolygonAPIError

    fake_client = _FakeClientForBinary(_FakeBinaryResponse(b"boom", 500))
    monkeypatch.setattr(client_mod, "ClientSession", lambda *a, **k: _FakeSessionCtx(fake_client))
    monkeypatch.setattr(client_mod, "create_signature", lambda *a, **k: "SIG")
    monkeypatch.setattr(client_mod, "time", lambda: 1700000000.0)

    with pytest.raises(PolygonAPIError) as exc:
        await polygon_call_binary("problem.package", {"packageId": "9"}, user)
    assert exc.value.http_status == 500
