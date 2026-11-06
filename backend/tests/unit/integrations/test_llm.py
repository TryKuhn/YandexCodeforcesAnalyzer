"""``/api/integrations/llm``: own LLM API keys, and handing them to the AI service only."""
import httpx
import pytest
from fastapi import HTTPException

import api.user.integrations.llm as llm
from api.crypt.secrets import encrypt
from models.user.integrations import LLMApiKey


@pytest.fixture
def provider(monkeypatch):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        key = request.headers.get("x-api-key") or request.headers.get("authorization", "").removeprefix("Bearer ")
        if key.endswith("bad"):
            return httpx.Response(401, json={"error": {"type": "authentication_error", "message": "invalid x-api-key"}})
        if key.endswith("down"):
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, json={"data": []})

    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))
    return seen


async def test_link_verifies_and_stores_encrypted(provider, db, user):
    status = await llm.llm_link(llm.LLMKeyIn(provider="anthropic", api_key="sk-ant-api03-0123456789good"),
                                user_id=user.id, db=db)
    assert status["providers"]["anthropic"] == {"linked": True, "hint": "sk-ant…good",
                                                "updated_at": status["providers"]["anthropic"]["updated_at"]}
    assert status["providers"]["openai"]["linked"] is False
    request = provider[-1]
    assert request.url.host == "api.anthropic.com" and request.headers["anthropic-version"]
    row = (await llm._rows(user.id, db))["anthropic"]
    assert "0123456789" not in row.key_enc

    await llm.llm_link(llm.LLMKeyIn(provider="openai", api_key="sk-proj-0123456789good"), user_id=user.id, db=db)
    assert provider[-1].url.host == "api.openai.com"
    assert provider[-1].headers["authorization"] == "Bearer sk-proj-0123456789good"


async def test_rejected_and_unreachable_keys(provider, db, user):
    with pytest.raises(HTTPException) as e:
        await llm.llm_link(llm.LLMKeyIn(provider="openrouter", api_key="sk-or-v1-bad"), user_id=user.id, db=db)
    assert e.value.status_code == 400 and "OpenRouter отклонил ключ: invalid x-api-key" in e.value.detail
    with pytest.raises(HTTPException) as e:
        await llm.llm_link(llm.LLMKeyIn(provider="openrouter", api_key="sk-or-v1-down"), user_id=user.id, db=db)
    assert e.value.status_code == 502
    assert await llm._rows(user.id, db) == {}


async def test_relink_replaces_and_unlink(provider, db, user):
    for key in ("sk-or-v1-first-key", "sk-or-v1-second-key"):
        await llm.llm_link(llm.LLMKeyIn(provider="openrouter", api_key=key), user_id=user.id, db=db)
    rows = await llm._rows(user.id, db)
    assert list(rows) == ["openrouter"] and rows["openrouter"].key_hint.endswith("-key")
    status = await llm.llm_unlink("openrouter", user_id=user.id, db=db)
    assert status["providers"]["openrouter"]["linked"] is False


async def test_resolve_is_only_for_the_ai_service(db, user):
    db.add(LLMApiKey(user_id=user.id, provider="anthropic", key_enc=encrypt("sk-ant-secret"), key_hint="h"))
    db.add(LLMApiKey(user_id=user.id, provider="openai", key_enc="broken", key_hint="h"))
    await db.commit()
    with pytest.raises(HTTPException) as e:
        await llm.llm_resolve(payload={"user_id": user.id}, db=db)
    assert e.value.status_code == 403
    result = await llm.llm_resolve(payload={"user_id": user.id, "svc": "ai-authoring"}, db=db)
    assert result["keys"] == {"openrouter": None, "anthropic": "sk-ant-secret", "openai": None}
    assert "OpenAI" in result["errors"][0]


def test_key_validation():
    with pytest.raises(ValueError):
        llm.LLMKeyIn(provider="gemini", api_key="x" * 20)
    with pytest.raises(ValueError):
        llm.LLMKeyIn(provider="openai", api_key="short")
