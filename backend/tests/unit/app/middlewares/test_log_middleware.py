"""Unit tests for app/middlewares/log_middleware.py — LoggingMiddleware.dispatch."""
import logging

import pytest

from app.middlewares.log_middleware import LoggingMiddleware


class _URL:
    def __init__(self, path):
        self.path = path


class _Client:
    host = "1.2.3.4"


class _Request:
    def __init__(self, path="/api/foo", query=None, method="GET", client=_Client()):
        self.url = _URL(path)
        self.method = method
        self.client = client
        self.query_params = query or {}
        self.headers = {}


class _Response:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.headers = {}


def _middleware():
    # BaseHTTPMiddleware needs an app arg; a dummy is fine since we call dispatch directly.
    return LoggingMiddleware(app=lambda *a, **k: None)


@pytest.mark.asyncio
async def test_health_path_skips_logging():
    mw = _middleware()
    sentinel = _Response(200)

    async def call_next(req):
        return sentinel

    req = _Request(path="/api/health")
    result = await mw.dispatch(req, call_next)
    assert result is sentinel
    # health responses are returned untouched (no X-Process-Time header added)
    assert "X-Process-Time" not in sentinel.headers


@pytest.mark.asyncio
async def test_adds_process_time_header_on_success():
    mw = _middleware()

    async def call_next(req):
        return _Response(200)

    result = await mw.dispatch(_Request(), call_next)
    assert "X-Process-Time" in result.headers


@pytest.mark.asyncio
async def test_logs_warning_for_4xx(caplog):
    mw = _middleware()

    async def call_next(req):
        return _Response(404)

    with caplog.at_level(logging.WARNING, logger="app.http"):
        await mw.dispatch(_Request(query={"q": "x"}), call_next)
    assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.asyncio
async def test_logs_error_for_5xx(caplog):
    mw = _middleware()

    async def call_next(req):
        return _Response(503)

    with caplog.at_level(logging.ERROR, logger="app.http"):
        await mw.dispatch(_Request(), call_next)
    assert any(r.levelno == logging.ERROR for r in caplog.records)


@pytest.mark.asyncio
async def test_exception_is_logged_and_reraised(caplog):
    mw = _middleware()

    async def call_next(req):
        raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="app.http"):
        with pytest.raises(RuntimeError):
            await mw.dispatch(_Request(), call_next)
    assert any("boom" in r.getMessage() for r in caplog.records)
