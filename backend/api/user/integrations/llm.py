"""``/api/integrations/llm``: the user's own LLM API keys (bring your own key).

The AI authoring service uses them instead of the server's OpenRouter key:
an Anthropic / OpenAI key for that vendor's models (direct API), an OpenRouter
key for everything else. Only API keys work here -- consumer chat subscriptions
(Claude Pro/Max, ChatGPT Plus) have no API access.

Keys are validated with a cheap read-only call, stored encrypted and never
returned to the browser (only a hint like ``sk-ant…a1b2``). The decrypted keys
are given out only to the AI service (``/resolve``, a token with ``svc=ai-authoring``).
"""
from __future__ import annotations

import logging
from typing import Literal

import httpx
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_payload, get_current_user
from api.crypt.secrets import SecretError, decrypt, encrypt, hint
from api.user.integrations.base import integrations_router
from app.database import get_db
from models.user.integrations import LLMApiKey

logger = logging.getLogger(__name__)

Provider = Literal["openrouter", "anthropic", "openai"]
PROVIDERS: tuple[str, ...] = ("openrouter", "anthropic", "openai")
PROVIDER_NAMES = {"openrouter": "OpenRouter", "anthropic": "Anthropic", "openai": "OpenAI"}

AI_SERVICE_CLAIM = "ai-authoring"
ANTHROPIC_VERSION = "2026-10-21"

# a read-only request that fails on a bad key
CHECKS: dict[str, tuple[str, str]] = {
    "openrouter": ("https://openrouter.ai/api/v1/key", "bearer"),
    "anthropic": ("https://api.anthropic.com/v1/models?limit=1", "anthropic"),
    "openai": ("https://api.openai.com/v1/models", "bearer"),
}

# set by tests
_transport: httpx.AsyncBaseTransport | None = None


class LLMKeyIn(BaseModel):
    provider: Provider
    api_key: str = Field(min_length=8, max_length=500)
    verify: bool = True


def _headers(provider: str, key: str) -> dict[str, str]:
    if CHECKS[provider][1] == "anthropic":
        return {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}
    return {"Authorization": f"Bearer {key}"}


async def verify_key(provider: str, key: str) -> None:
    """HTTPException 400 for a rejected key, 502 when the provider can't be reached."""
    url = CHECKS[provider][0]
    name = PROVIDER_NAMES[provider]
    try:
        async with httpx.AsyncClient(timeout=20, transport=_transport) as client:
            response = await client.get(url, headers=_headers(provider, key))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"{name} недоступен, ключ не проверен: {e!r}") from e
    if response.status_code == 200:
        return
    detail = response.text[:300]
    try:
        err = response.json().get("error")
        detail = (err.get("message") if isinstance(err, dict) else err) or detail
    except (ValueError, AttributeError):
        pass
    if response.status_code in (400, 401, 403, 404):
        raise HTTPException(status_code=400, detail=f"{name} отклонил ключ: {detail}")
    raise HTTPException(status_code=502, detail=f"{name}: HTTP {response.status_code}, ключ не проверен: {detail}")


async def _rows(user_id: int, db: AsyncSession) -> dict[str, LLMApiKey]:
    rows = (await db.execute(select(LLMApiKey).where(LLMApiKey.user_id == user_id))).scalars().all()
    return {row.provider: row for row in rows}


def _status(rows: dict[str, LLMApiKey]) -> dict:
    return {
        "providers": {
            p: {
                "linked": p in rows,
                "hint": rows[p].key_hint if p in rows else None,
                "updated_at": rows[p].updated_at.isoformat() if p in rows and rows[p].updated_at else None,
            }
            for p in PROVIDERS
        }
    }


@integrations_router.get("/llm")
async def llm_status(user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return _status(await _rows(user_id, db))


@integrations_router.post("/llm")
async def llm_link(
    body: LLMKeyIn, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    key = body.api_key.strip()
    if body.verify:
        await verify_key(body.provider, key)
    rows = await _rows(user_id, db)
    row = rows.get(body.provider)
    if row is None:
        row = LLMApiKey(user_id=user_id, provider=body.provider)
        db.add(row)
    row.key_enc = encrypt(key)
    row.key_hint = hint(key)
    await db.commit()
    logger.info("LLM key linked: user_id=%s provider=%s", user_id, body.provider)
    return _status(await _rows(user_id, db))


@integrations_router.post("/llm/{provider}/unlink")
async def llm_unlink(
    provider: Provider, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    rows = await _rows(user_id, db)
    if provider in rows:
        await db.delete(rows[provider])
        await db.commit()
        rows.pop(provider)
    return _status(rows)


@integrations_router.get("/llm/resolve")
async def llm_resolve(payload: dict = Depends(get_current_payload), db: AsyncSession = Depends(get_db)) -> dict:
    """The user's decrypted keys -- for the AI service only (its own token, ``svc=ai-authoring``)."""
    if payload.get("svc") != AI_SERVICE_CLAIM or not payload.get("user_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only for the AI service")
    keys: dict[str, str | None] = {p: None for p in PROVIDERS}
    errors: list[str] = []
    for provider, row in (await _rows(int(payload["user_id"]), db)).items():
        try:
            keys[provider] = decrypt(row.key_enc)
        except SecretError as e:
            errors.append(f"{PROVIDER_NAMES.get(provider, provider)}: {e}")
    return {"keys": keys, "errors": errors}
