import json

import httpx
import pytest

from authoring.llm import client as client_module
from authoring.llm import credentials as cred_module
from authoring.llm.client import (
    Credentials,
    LLMClient,
    LLMError,
    Msg,
    Part,
    render_anthropic,
    render_messages,
    route_for,
)
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


async def test_error_inside_200_choice_is_retried():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": ""}, "finish_reason": "error",
                                                          "error": {"message": "upstream reset"}}]})
        return ok("fine")

    result = await LLMClient(transport=httpx.MockTransport(handler)).complete("m", [Msg.text("user", "q")])
    assert result.text == "fine" and calls == 2


async def test_empty_answer_is_an_error_after_retries():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return ok("   ")

    with pytest.raises(LLMError, match="пустой ответ"):
        await LLMClient(transport=httpx.MockTransport(handler)).complete("m", [Msg.text("user", "q")])
    assert calls == client_module._MAX_ATTEMPTS


# --------------------------------------------------------------------------- own keys (BYOK)
OWN = Credentials(openrouter="sk-or-user", anthropic="sk-ant-user", openai="sk-proj-user")


def anthropic_ok(text="hi", stop="end_turn"):
    return httpx.Response(200, json={
        "model": "claude-opus-5-5", "stop_reason": stop,
        "content": [{"type": "thinking", "thinking": "", "signature": "x"}, {"type": "text", "text": text}],
        "usage": {"input_tokens": 3, "output_tokens": 1},
    })


def test_routing_prefers_the_vendor_key_then_own_openrouter_then_ours():
    from authoring.settings import settings

    assert route_for("anthropic/claude-opus-5.5", None).key == settings.OPENAI_API_KEY
    assert not route_for("m", None).own_key
    r = route_for("anthropic/claude-opus-5.5", OWN)
    assert (r.provider, r.model, r.key, r.own_key) == ("anthropic", "claude-opus-5-5", "sk-ant-user", True)
    r = route_for("anthropic/claude-haiku-5.5", OWN)
    assert r.model == "claude-haiku-5-5"
    r = route_for("openai/gpt-6.1-sol", OWN)
    assert (r.provider, r.model, r.key) == ("openai", "gpt-6.1-sol", "sk-proj-user")
    # a vendor key does not cover the other vendor's models: own OpenRouter key, else ours
    only_anthropic = Credentials(anthropic="sk-ant-user")
    assert route_for("openai/gpt-6.1-sol", only_anthropic).provider == "openrouter"
    assert route_for("openai/gpt-6.1-sol", only_anthropic).own_key is False
    r = route_for("openai/gpt-6.1-sol", Credentials(openrouter="sk-or-user"))
    assert (r.provider, r.model, r.key, r.own_key) == ("openrouter", "openai/gpt-6.1-sol", "sk-or-user", True)
    # unknown direct id: never sent to the vendor API
    assert route_for("anthropic/claude-unknown", OWN).provider == "openrouter"


def test_anthropic_rendering_keeps_cache_and_merges_turns():
    msgs = [Msg.text("system", "sys"), Msg("user", [Part("materials", cache=True), Part("")]),
            Msg.text("user", "question"), Msg.text("assistant", "a"), Msg.text("user", "fix")]
    system, turns = render_anthropic(msgs, json_mode=True)
    assert system[0] == {"type": "text", "text": "sys"} and "JSON" in system[-1]["text"]
    assert [t["role"] for t in turns] == ["user", "assistant", "user"]
    assert turns[0]["content"] == [
        {"type": "text", "text": "materials", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "question"},
    ]


async def test_own_anthropic_key_uses_the_messages_api():
    seen = []

    def handler(request):
        seen.append(request)
        return anthropic_ok("answer", "max_tokens")

    client = LLMClient(httpx.MockTransport(handler), credentials=OWN)
    result = await client.complete("anthropic/claude-opus-5.5", [Msg.text("system", "s"), Msg.text("user", "q")])
    assert result.text == "answer" and result.truncated
    request = seen[0]
    body = json.loads(request.content)
    assert request.url.host == "api.anthropic.com" and request.headers["x-api-key"] == "sk-ant-user"
    assert request.headers["anthropic-version"] and "authorization" not in request.headers
    assert body["model"] == "claude-opus-5-5" and body["system"] == [{"type": "text", "text": "s"}]
    assert body["max_tokens"] > 0 and "temperature" not in body


async def test_own_openai_key_uses_the_openai_api():
    seen = []

    def handler(request):
        seen.append(request)
        return ok("{}")

    client = LLMClient(httpx.MockTransport(handler), credentials=OWN)
    await client.complete("openai/gpt-6.1-sol", [Msg.text("user", "q")], json_mode=True)
    body = json.loads(seen[0].content)
    assert seen[0].url.host == "api.openai.com" and seen[0].headers["authorization"] == "Bearer sk-proj-user"
    assert body["model"] == "gpt-6.1-sol" and body["max_completion_tokens"] > 0 and "max_tokens" not in body
    assert body["response_format"] == {"type": "json_object"}


async def test_own_openrouter_key_replaces_ours():
    seen = []

    def handler(request):
        seen.append(request)
        return ok("x")

    client = LLMClient(httpx.MockTransport(handler), credentials=Credentials(openrouter="sk-or-user"))
    await client.complete("anthropic/claude-opus-5.5", [Msg.text("user", "q")])
    assert seen[0].url.host == "openrouter.ai" and seen[0].headers["authorization"] == "Bearer sk-or-user"


async def test_rejected_own_key_is_a_clear_error_without_fallback():
    calls = []

    def handler(request):
        calls.append(request.url.host)
        return httpx.Response(401, json={"type": "error", "error": {"type": "authentication_error",
                                                                     "message": "invalid x-api-key"}})

    client = LLMClient(httpx.MockTransport(handler), credentials=OWN)
    with pytest.raises(LLMError, match="Ваш ключ Anthropic отклонён: invalid x-api-key") as e:
        await client.complete_any(["anthropic/claude-haiku-5.5", "anthropic/claude-sonnet-5.5"],
                                  [Msg.text("user", "q")])
    assert calls == ["api.anthropic.com"] and not e.value.fallback_ok


async def test_own_key_without_credits():
    def handler(request):
        return httpx.Response(400, json={"type": "error", "error": {
            "type": "invalid_request_error", "message": "Your credit balance is too low"}})

    client = LLMClient(httpx.MockTransport(handler), credentials=OWN)
    with pytest.raises(LLMError, match="На балансе вашего ключа Anthropic недостаточно средств"):
        await client.complete("anthropic/claude-opus-5.5", [Msg.text("user", "q")])


async def test_anthropic_overload_is_retried_and_refusal_is_reported():
    answers = iter([httpx.Response(529, json={"error": {"message": "Overloaded"}}), anthropic_ok("fine")])
    client = LLMClient(httpx.MockTransport(lambda r: next(answers)), credentials=OWN)
    assert (await client.complete("anthropic/claude-opus-5.5", [Msg.text("user", "q")])).text == "fine"

    refusal = httpx.Response(200, json={"content": [], "stop_reason": "refusal",
                                        "stop_details": {"type": "refusal", "explanation": "no"}})
    client = LLMClient(httpx.MockTransport(lambda r: refusal), credentials=OWN)
    with pytest.raises(LLMError, match="отказалась"):
        await client.complete("anthropic/claude-opus-5.5", [Msg.text("user", "q")])


async def test_credentials_are_fetched_with_a_service_token_and_cached(monkeypatch):
    import jwt

    from authoring.settings import settings

    cred_module.invalidate()
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"keys": {"openrouter": None, "anthropic": "sk-ant-user", "openai": None},
                                         "errors": []})

    transport = httpx.MockTransport(handler)
    first = await cred_module.credentials_for(7, transport=transport)
    again = await cred_module.credentials_for(7, transport=transport)
    assert first == again == Credentials(anthropic="sk-ant-user") and len(seen) == 1
    assert seen[0].url.path.endswith("/integrations/llm/resolve")
    token = seen[0].headers["authorization"].removeprefix("Bearer ")
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert claims["user_id"] == 7 and claims["svc"] == "ai-authoring"

    cred_module.invalidate(7)
    monkeypatch.setattr(settings, "LLM_CREDENTIALS_TTL_SECONDS", 0)
    with pytest.raises(LLMError, match="ключи ИИ"):
        await cred_module.credentials_for(7, transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert await cred_module.fetch_credentials(
        7, transport=httpx.MockTransport(lambda r: httpx.Response(404))) == Credentials()
    cred_module.invalidate()


async def test_user_llm_resolves_keys_lazily():
    fetched = []

    async def fetch(user_id):
        fetched.append(user_id)
        return Credentials(openrouter="sk-or-user")

    seen = []

    def handler(request):
        seen.append(request)
        return ok("x")

    user_llm = cred_module.UserLLM(5, fetch=fetch, transport=httpx.MockTransport(handler))
    assert fetched == []
    await user_llm.complete_any(["m"], [Msg.text("user", "q")])
    assert fetched == [5] and seen[0].headers["authorization"] == "Bearer sk-or-user"


def test_worker_uses_per_user_llm_only_for_the_real_client():
    from authoring.llm.client import llm as default_llm
    from authoring.pipeline.runner import Worker

    fake = object()
    assert Worker(llm=fake).llm_factory(1) is fake  # type: ignore[arg-type]
    assert isinstance(Worker(llm=default_llm).llm_factory(1), cred_module.UserLLM)
