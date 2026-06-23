"""Unit tests for api.user.polygon.get_response.

``get_response`` POSTs via ``client.post(url, data=params)`` used as an async
context manager, reads the body, then:
  * JSON with status OK   -> returns result["result"]
  * JSON with status OK but no "result" key -> {"message": <text>}
  * JSON with status FAILED -> raises PolygonAPIError (comment)
  * non-JSON, status 200   -> {"message": <text>}
  * non-JSON, status != 200 -> raises PolygonAPIError

We fake ``ClientSession.post`` with an async-context-manager that yields a fake
response exposing ``.read()`` (async) and ``.status``.
"""
import json

import pytest

from api.user.polygon.get_response import PolygonAPIError, get_response


class _FakeResponse:
    def __init__(self, body: bytes, status: int):
        self._body = body
        self.status = status

    async def read(self):
        return self._body


class _FakePostCtx:
    """Async context manager returned by client.post(...)."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class _FakeClient:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def post(self, url, data=None):
        self.calls.append((url, data))
        return _FakePostCtx(self._response)


def _client(body, status=200):
    if isinstance(body, str):
        body = body.encode("utf-8")
    return _FakeClient(_FakeResponse(body, status))


async def test_json_status_ok_returns_result():
    payload = json.dumps({"status": "OK", "result": {"id": 7}})
    client = _client(payload, 200)
    result = await get_response(client, "http://x/problem.info", {"a": "1"})
    assert result == {"id": 7}


async def test_json_status_ok_passes_params_to_post():
    payload = json.dumps({"status": "OK", "result": []})
    client = _client(payload, 200)
    await get_response(client, "http://x/m", {"apiKey": "k"})
    assert client.calls == [("http://x/m", {"apiKey": "k"})]


async def test_json_status_ok_missing_result_returns_message():
    payload = json.dumps({"status": "OK"})  # no "result" key
    client = _client(payload, 200)
    result = await get_response(client, "http://x/m", {})
    assert result == {"message": payload}


async def test_json_status_failed_raises_with_comment():
    payload = json.dumps({"status": "FAILED", "comment": "bad problemId"})
    client = _client(payload, 200)
    with pytest.raises(PolygonAPIError) as exc:
        await get_response(client, "http://x/m", {})
    assert "bad problemId" in str(exc.value)
    assert exc.value.message == "bad problemId"


async def test_json_status_failed_default_comment():
    payload = json.dumps({"status": "FAILED"})
    client = _client(payload, 200)
    with pytest.raises(PolygonAPIError) as exc:
        await get_response(client, "http://x/m", {})
    assert str(exc.value) == "Unknown Polygon error"


async def test_non_json_200_returns_message_wrapper():
    client = _client("plain file body", 200)
    result = await get_response(client, "http://x/m", {})
    assert result == {"message": "plain file body"}


async def test_non_json_non_200_raises_polygon_error():
    client = _client("<html>500</html>", 500)
    with pytest.raises(PolygonAPIError) as exc:
        await get_response(client, "http://x/m", {})
    assert exc.value.http_status == 500
    assert "HTTP 500" in str(exc.value)
    assert exc.value.raw_response == "<html>500</html>"


async def test_non_json_non_200_truncates_body_to_300():
    long_body = "E" * 1000
    client = _client(long_body, 502)
    with pytest.raises(PolygonAPIError) as exc:
        await get_response(client, "http://x/m", {})
    # Message includes only first 300 chars of the body.
    assert ("E" * 300) in str(exc.value)
    assert ("E" * 301) not in str(exc.value)
    # raw_response keeps the full text.
    assert exc.value.raw_response == long_body


async def test_invalid_utf8_is_decoded_tolerantly():
    # 0xff is not valid UTF-8; decode(errors="replace") must not raise.
    client = _client(b"\xff\xfe binary", 200)
    result = await get_response(client, "http://x/m", {})
    assert "message" in result


# --- PolygonAPIError class ------------------------------------------------

def test_polygon_error_defaults():
    err = PolygonAPIError("boom")
    assert err.message == "boom"
    assert err.http_status is None
    assert err.raw_response is None
    assert str(err) == "boom"


def test_polygon_error_attributes():
    err = PolygonAPIError("oops", http_status=404, raw_response="raw")
    assert err.http_status == 404
    assert err.raw_response == "raw"
    assert str(err) == "oops"
    assert isinstance(err, Exception)
