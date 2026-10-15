import json

import httpx
import pytest

from authoring.llm import client as client_module
from authoring.llm.client import LLMClient, LLMError, Msg, Part, render_messages
from authoring.llm.models import DEFAULT_MODEL, normalize_model


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def instant(_):
        return None
    monkeypatch.setattr(client_module.asyncio, "sleep", instant)


def ok(text="hi", finish="stop"):
    return httpx.Response(200, json={"model": "m", "choices": [{"message": {"content": text}, "finish_reason": finish}],
                                     "usage": {"total_tokens": 3}})


def test_registry_defaults_and_legacy_ids():
    assert DEFAULT_MODEL == "anthropic/claude-opus-5.5"
    assert normalize_model(None) == DEFAULT_MODEL
    assert normalize_model("anthropic/claude-sonnet-4.6") == "anthropic/claude-sonnet-5.5"
    assert normalize_model("openai/gpt-5.5-pro") == "openai/gpt-6.1-sol"
    assert normalize_model("evil/model") == DEFAULT_MODEL


def test_cache_control_only_for_anthropic():
    msgs = [Msg.text("system", "sys"), Msg("user", [Part("materials", cache=True), Part("question")])]
    rendered = render_messages("anthropic/claude-opus-5.5", msgs)
    assert rendered[0] == {"role": "system", "content": "sys"}
    assert rendered[1]["content"][0] == {"type": "text", "text": "materials", "cache_control": {"type": "ephemeral"}}
    assert "cache_control" not in rendered[1]["content"][1]
    plain = render_messages("openai/gpt-6.1-sol", msgs)
    assert plain[1] == {"role": "user", "content": "materials\n\nquestion"}


async def test_retries_transient_errors_and_sends_payload():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(502, text="bad gateway") if len(seen) < 3 else ok("done", "length")

    result = await LLMClient(transport=httpx.MockTransport(handler)).complete(
        "anthropic/claude-opus-5.5", [Msg.text("user", "q")], json_mode=True
    )
    assert result.text == "done" and result.truncated
    assert len(seen) == 3
    assert seen[0]["response_format"] == {"type": "json_object"}
    assert seen[0]["max_tokens"] > 0


async def test_payment_error_is_not_retried():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(402, json={"error": {"message": "Insufficient credits"}})

    with pytest.raises(LLMError, match="OpenRouter") as e:
        await LLMClient(transport=httpx.MockTransport(handler)).complete("m", [Msg.text("user", "q")])
    assert calls == 1 and not e.value.fallback_ok


async def test_region_block_falls_back_to_next_model():
    def handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        if model == "anthropic/claude-haiku-5.5":
            return httpx.Response(403, json={"error": {"message": "Request not allowed in your region"}})
        return ok(model)

    result = await LLMClient(transport=httpx.MockTransport(handler)).complete_any(
        ["anthropic/claude-haiku-5.5", "anthropic/claude-sonnet-5.5"], [Msg.text("user", "q")]
    )
    assert result.text == "anthropic/claude-sonnet-5.5"


async def test_content_blocks_are_joined():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": [{"type": "text", "text": "a"},
                                                                              {"type": "text", "text": "b"}]}}]})

    result = await LLMClient(transport=httpx.MockTransport(handler)).complete("m", [Msg.text("user", "q")])
    assert result.text == "ab"


async def test_read_timeout_is_not_retried():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMError, match="не ответила"):
        await LLMClient(transport=httpx.MockTransport(handler)).complete("m", [Msg.text("user", "q")])
    assert calls == 1
