"""Unit tests for app/server.py — exception handlers and async helpers."""
import json

import pytest

import app.server as server
from api.user.polygon.get_response import PolygonAPIError


class _FakeValidationError:
    def __init__(self, errors):
        self._errors = errors

    def errors(self):
        return self._errors


def _body(response):
    return json.loads(bytes(response.body).decode())


@pytest.mark.asyncio
async def test_validation_handler_value_error_returns_400():
    exc = _FakeValidationError([
        {"type": "value_error", "ctx": {"error": "name too long"}},
    ])
    resp = await server.validation_exception_handler(request=None, exc=exc)
    assert resp.status_code == 400
    assert _body(resp)["detail"] == "name too long"


@pytest.mark.asyncio
async def test_validation_handler_other_returns_422():
    exc = _FakeValidationError([{"type": "missing"}])
    resp = await server.validation_exception_handler(request=None, exc=exc)
    assert resp.status_code == 422
    assert _body(resp)["detail"] == "Validation error"


@pytest.mark.asyncio
async def test_polygon_api_error_handler_uses_http_status():
    exc = PolygonAPIError("boom", http_status=403)
    resp = await server.polygon_api_error_handler(request=None, exc=exc)
    assert resp.status_code == 403
    assert _body(resp)["detail"] == "boom"


@pytest.mark.asyncio
async def test_polygon_api_error_handler_defaults_to_400():
    exc = PolygonAPIError("oops")
    resp = await server.polygon_api_error_handler(request=None, exc=exc)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_global_exception_handler_returns_500():
    class _Req:
        method = "GET"

        class url:
            path = "/x"

    resp = await server.global_exception_handler(request=_Req(), exc=RuntimeError("x"))
    assert resp.status_code == 500
    assert _body(resp)["detail"] == "Internal server error"


def test_app_is_fastapi_instance():
    from fastapi import FastAPI

    assert isinstance(server.app, FastAPI)


@pytest.mark.asyncio
async def test_cleanup_expired_tokens_handles_exception(monkeypatch):
    """One iteration: Session raises, the loop logs and then sleeps -> we break
    out by making asyncio.sleep raise a sentinel to stop the infinite loop."""
    class _Boom:
        def __call__(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(server, "Session", _Boom())

    class _Stop(Exception):
        pass

    async def fake_sleep(_):
        raise _Stop()

    monkeypatch.setattr(server.asyncio, "sleep", fake_sleep)

    with pytest.raises(_Stop):
        await server.cleanup_expired_tokens()
