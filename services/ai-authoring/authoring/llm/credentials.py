"""The user's own LLM API keys, fetched from the backend (profile -> "ИИ-модели").

The backend keeps the keys encrypted and gives them out only to this service
(``GET /api/integrations/llm/resolve`` with our ``svc=ai-authoring`` token).
They are cached for ``LLM_CREDENTIALS_TTL_SECONDS`` so a run of a dozen model
calls asks the backend once.

:func:`for_user` returns an :class:`~authoring.llm.client.LLM` that resolves
the keys lazily on its first call, so building it costs nothing.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Sequence

import httpx

from authoring.auth import mint_user_token
from authoring.llm.client import LLM, Completion, Credentials, LLMClient, LLMError, Msg
from authoring.settings import settings

logger = logging.getLogger(__name__)

RESOLVE_PATH = "/integrations/llm/resolve"

# user_id -> (fetched at, credentials)
_cache: dict[int, tuple[float, Credentials]] = {}


def invalidate(user_id: int | None = None) -> None:
    if user_id is None:
        _cache.clear()
    else:
        _cache.pop(user_id, None)


async def fetch_credentials(user_id: int, *, transport: httpx.AsyncBaseTransport | None = None) -> Credentials:
    """The user's keys from the backend; LLMError when the backend can't tell."""
    headers = {"Authorization": f"Bearer {mint_user_token(user_id)}"}
    try:
        async with httpx.AsyncClient(
            base_url=settings.BACKEND_API_URL.rstrip("/"), timeout=20, transport=transport
        ) as http:
            response = await http.get(RESOLVE_PATH, headers=headers)
    except httpx.HTTPError as e:
        raise LLMError(f"Не удалось получить ваши ключи ИИ из профиля: backend недоступен ({e!r})") from e
    if response.status_code == 404:
        # an older backend without the integration: nobody has own keys
        return Credentials()
    if response.status_code != 200:
        raise LLMError(f"Не удалось получить ваши ключи ИИ из профиля: HTTP {response.status_code}")
    data = response.json()
    for error in data.get("errors") or []:
        logger.warning("user %s: own LLM key unreadable: %s", user_id, error)
    keys = data.get("keys") or {}
    return Credentials(
        openrouter=keys.get("openrouter") or None,
        anthropic=keys.get("anthropic") or None,
        openai=keys.get("openai") or None,
    )


async def credentials_for(user_id: int, *, transport: httpx.AsyncBaseTransport | None = None) -> Credentials:
    now = time.monotonic()
    cached = _cache.get(user_id)
    if cached is not None and now - cached[0] < settings.LLM_CREDENTIALS_TTL_SECONDS:
        return cached[1]
    credentials = await fetch_credentials(user_id, transport=transport)
    _cache[user_id] = (now, credentials)
    return credentials


Fetch = Callable[[int], Awaitable[Credentials]]


class UserLLM:
    """An :class:`LLM` that calls the models with ``user_id``'s own keys (if any)."""

    def __init__(
        self,
        user_id: int,
        *,
        fetch: Fetch = credentials_for,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.user_id = user_id
        self._fetch = fetch
        self._transport = transport

    async def _client(self) -> LLMClient:
        return LLMClient(self._transport, credentials=await self._fetch(self.user_id))

    async def complete(
        self, model: str, messages: Sequence[Msg], *, max_tokens: int | None = None, json_mode: bool = False
    ) -> Completion:
        client = await self._client()
        return await client.complete(model, messages, max_tokens=max_tokens, json_mode=json_mode)

    async def complete_any(
        self, models: Sequence[str], messages: Sequence[Msg], *, max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> Completion:
        client = await self._client()
        return await client.complete_any(models, messages, max_tokens=max_tokens, json_mode=json_mode)


def for_user(user_id: int) -> LLM:
    return UserLLM(user_id)
