"""Unit tests for api/user/codeforces/get_response.py — CF API response parsing."""
import json

import pytest
from fastapi import HTTPException

from api.user.codeforces.get_response import get_response


class _FakeResponse:
    def __init__(self, text: str, status: int = 200):
        self._text = text
        self.status = status

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeClient:
    """Mimics aiohttp.ClientSession.post -> async context manager."""

    def __init__(self, response: _FakeResponse):
        self._response = response
        self.calls: list = []

    def post(self, url, data):
        self.calls.append((url, data))
        return self._response


@pytest.mark.asyncio
async def test_ok_returns_result_field():
    body = json.dumps({"status": "OK", "result": [{"handle": "tourist"}]})
    client = _FakeClient(_FakeResponse(body))
    result = await get_response(client, "http://cf/api", {"a": "1"})
    assert result == [{"handle": "tourist"}]
    assert client.calls == [("http://cf/api", {"a": "1"})]


@pytest.mark.asyncio
async def test_ok_without_result_returns_message():
    # status OK but no "result" key — note source catches KeyError.
    body = json.dumps({"status": "OK"})
    client = _FakeClient(_FakeResponse(body))
    result = await get_response(client, "u", {})
    assert result == {"message": body}


@pytest.mark.asyncio
async def test_failed_status_raises_400_with_comment():
    body = json.dumps({"status": "FAILED", "comment": "apiKey invalid"})
    client = _FakeClient(_FakeResponse(body))
    with pytest.raises(HTTPException) as exc:
        await get_response(client, "u", {})
    assert exc.value.status_code == 400
    assert exc.value.detail == "apiKey invalid"


@pytest.mark.asyncio
async def test_non_json_non_200_raises_400():
    client = _FakeClient(_FakeResponse("Internal Server Error", status=500))
    with pytest.raises(HTTPException) as exc:
        await get_response(client, "u", {})
    assert exc.value.status_code == 400
    assert "HTTP 500" in exc.value.detail


@pytest.mark.asyncio
async def test_non_json_200_returns_message():
    client = _FakeClient(_FakeResponse("plain text body", status=200))
    result = await get_response(client, "u", {})
    assert result == {"message": "plain text body"}
