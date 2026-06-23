"""Unit tests for LLMClient.ask / ask_text network behaviour (services.llm.client).

httpx.AsyncClient is replaced with a fake async context manager whose ``post``
returns a canned response object exposing ``status_code``, ``.json()`` and
``.text``. strip_code_fences is covered in test_client.py; not duplicated here.
"""
import json

import httpx
import pytest
from fastapi import HTTPException

from api.user.gpt.services.llm import client as client_mod
from api.user.gpt.services.llm.client import LLMClient


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _content_payload(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def _install_fake_client(monkeypatch, *, response=None, post_exc=None):
    """Patch httpx.AsyncClient in the module under test with a fake.

    Returns a dict capturing the post() call arguments.
    """
    captured = {}

    class _FakeClient:
        def __init__(self, *a, **kw):
            captured["init"] = (a, kw)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            if post_exc is not None:
                raise post_exc
            return response

    monkeypatch.setattr(client_mod.httpx, "AsyncClient", _FakeClient)
    return captured


@pytest.mark.asyncio
async def test_ask_json_mode_parses_dict(monkeypatch):
    resp = _FakeResponse(200, _content_payload('{"a": 1, "b": "x"}'))
    captured = _install_fake_client(monkeypatch, response=resp)
    out = await LLMClient().ask("m", [{"role": "user", "content": "hi"}])
    assert out == {"a": 1, "b": "x"}
    # json_mode=True adds response_format
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["json"]["model"] == "m"


@pytest.mark.asyncio
async def test_ask_json_mode_strips_code_fence(monkeypatch):
    resp = _FakeResponse(200, _content_payload('```json\n{"k": 5}\n```'))
    _install_fake_client(monkeypatch, response=resp)
    out = await LLMClient().ask("m", [])
    assert out == {"k": 5}


@pytest.mark.asyncio
async def test_ask_non_json_mode_returns_text_wrapper(monkeypatch):
    resp = _FakeResponse(200, _content_payload("plain text answer"))
    captured = _install_fake_client(monkeypatch, response=resp)
    out = await LLMClient().ask("m", [], json_mode=False)
    assert out == {"text": "plain text answer"}
    # json_mode=False → no response_format key
    assert "response_format" not in captured["json"]


@pytest.mark.asyncio
async def test_ask_non_200_raises_500(monkeypatch):
    resp = _FakeResponse(503, payload=None, text="upstream down")
    _install_fake_client(monkeypatch, response=resp)
    with pytest.raises(HTTPException) as ei:
        await LLMClient().ask("m", [])
    assert ei.value.status_code == 500
    assert "upstream down" in ei.value.detail


@pytest.mark.asyncio
async def test_ask_jsondecode_fallback_regex(monkeypatch):
    # Content is not pure JSON but contains a JSON object → regex fallback.
    resp = _FakeResponse(200, _content_payload('Here is the answer: {"x": 42} thanks'))
    _install_fake_client(monkeypatch, response=resp)
    out = await LLMClient().ask("m", [])
    assert out == {"x": 42}


@pytest.mark.asyncio
async def test_ask_unparseable_json_raises_500(monkeypatch):
    # No JSON object at all → inner JSONDecodeError re-raised → caught → 500.
    resp = _FakeResponse(200, _content_payload("not json at all"))
    _install_fake_client(monkeypatch, response=resp)
    with pytest.raises(HTTPException) as ei:
        await LLMClient().ask("m", [])
    assert ei.value.status_code == 500


@pytest.mark.asyncio
async def test_ask_connect_error_raises_503(monkeypatch):
    _install_fake_client(monkeypatch, post_exc=httpx.ConnectError("boom"))
    with pytest.raises(HTTPException) as ei:
        await LLMClient().ask("m", [])
    assert ei.value.status_code == 503
    assert "unavailable" in ei.value.detail.lower()


@pytest.mark.asyncio
async def test_ask_timeout_raises_503(monkeypatch):
    _install_fake_client(monkeypatch, post_exc=httpx.TimeoutException("slow"))
    with pytest.raises(HTTPException) as ei:
        await LLMClient().ask("m", [])
    assert ei.value.status_code == 503


@pytest.mark.asyncio
async def test_ask_unexpected_error_raises_500(monkeypatch):
    _install_fake_client(monkeypatch, post_exc=RuntimeError("weird"))
    with pytest.raises(HTTPException) as ei:
        await LLMClient().ask("m", [])
    assert ei.value.status_code == 500


@pytest.mark.asyncio
async def test_ask_text_wrapper_strips(monkeypatch):
    resp = _FakeResponse(200, _content_payload("  hello world  "))
    _install_fake_client(monkeypatch, response=resp)
    out = await LLMClient().ask_text("m", [])
    assert out == "hello world"


@pytest.mark.asyncio
async def test_ask_text_missing_text_returns_empty(monkeypatch):
    # ask returns {"text": content}; if content empty, ask_text → "".
    resp = _FakeResponse(200, _content_payload(""))
    _install_fake_client(monkeypatch, response=resp)
    out = await LLMClient().ask_text("m", [])
    assert out == ""
