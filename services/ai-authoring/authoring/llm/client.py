"""Async client for the OpenRouter chat-completions API.

* transient failures (429, 5xx, network) are retried with back-off;
* a provider refusal (403 "not allowed" / region block) is retried a couple of
  times -- OpenRouter routes every request independently, so a retry may land
  on an allowed provider -- and then reported as ``fallback_ok`` so
  :meth:`LLMClient.complete_any` moves on to the next model;
* Anthropic models get ``cache_control`` on the blocks marked cacheable (the
  problem materials), which makes repeated calls over the same problem cheap.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from authoring.llm.models import is_anthropic
from authoring.settings import settings

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 4


class LLMError(Exception):
    """A failed LLM call with a short human-readable (Russian) message."""

    def __init__(self, message: str, *, status: int | None = None, fallback_ok: bool = False):
        super().__init__(message)
        self.message = message
        self.status = status
        # True when another model may succeed (provider block, unknown model)
        self.fallback_ok = fallback_ok


@dataclass
class Part:
    """A piece of a message; ``cache`` marks the stable prefix (problem materials)."""

    text: str
    cache: bool = False


@dataclass
class Msg:
    role: str  # system | user | assistant
    parts: list[Part] = field(default_factory=list)

    @classmethod
    def text(cls, role: str, text: str, *, cache: bool = False) -> Msg:
        return cls(role, [Part(text, cache)])


@dataclass
class Completion:
    text: str
    model: str
    truncated: bool = False
    usage: dict = field(default_factory=dict)


class LLM(Protocol):
    """What the pipeline needs from a client (tests substitute a fake)."""

    async def complete(
        self,
        model: str,
        messages: Sequence[Msg],
        *,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> Completion: ...

    async def complete_any(
        self,
        models: Sequence[str],
        messages: Sequence[Msg],
        *,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> Completion: ...


def _looks_like_provider_block(text: str) -> bool:
    low = (text or "").lower()
    return any(k in low for k in ("not allowed", "region", "country", "territory", "unsupported_country"))


def _error_message(status: int, body: str) -> str:
    """Pull the useful message out of OpenRouter's nested error JSON."""
    message = body
    try:
        data = json.loads(body)
        err = data.get("error", data) if isinstance(data, dict) else {}
        message = err.get("message") or message
        raw = (err.get("metadata") or {}).get("raw")
        if isinstance(raw, str) and raw:
            try:
                message = json.loads(raw).get("error", {}).get("message") or message
            except (ValueError, AttributeError):
                message = raw
    except (ValueError, AttributeError, TypeError):
        pass
    low = (message or "").lower()
    if status == 402 or "credit" in low or "afford" in low:
        return "Недостаточно средств на балансе OpenRouter для этого запроса."
    if status == 403 and _looks_like_provider_block(low):
        return "Провайдер модели отклонил запрос (вероятно, региональная блокировка)."
    return (message or f"HTTP {status}")[:400]


def render_messages(model: str, messages: Sequence[Msg]) -> list[dict[str, Any]]:
    """OpenAI-format messages; cache markers become ``cache_control`` for Anthropic."""
    anthropic = is_anthropic(model)
    out: list[dict[str, Any]] = []
    for msg in messages:
        if not anthropic or not any(p.cache for p in msg.parts):
            out.append({"role": msg.role, "content": "\n\n".join(p.text for p in msg.parts)})
            continue
        blocks: list[dict[str, Any]] = []
        for part in msg.parts:
            block: dict[str, Any] = {"type": "text", "text": part.text}
            if part.cache:
                block["cache_control"] = {"type": "ephemeral"}
            blocks.append(block)
        out.append({"role": msg.role, "content": blocks})
    return out


class LLMClient:
    """OpenRouter client; one shared instance per process."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        base = settings.OPENAI_HOST.rstrip("/")
        self.url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://createmanager.duckdns.org",
            "X-Title": "Createmanager AI authoring",
        }

    async def complete(
        self,
        model: str,
        messages: Sequence[Msg],
        *,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> Completion:
        payload: dict[str, Any] = {
            "model": model,
            "messages": render_messages(model, messages),
            # always capped: OpenRouter reserves max_tokens in its affordability check
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
            "usage": {"include": True},
        }
        if settings.openrouter_provider:
            payload["provider"] = settings.openrouter_provider
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_error: LLMError | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=settings.LLM_TIMEOUT_SECONDS, transport=self._transport
                ) as http:
                    response = await http.post(self.url, headers=self._headers(), json=payload)
            except httpx.ReadTimeout as e:
                # the model may still be generating (and billing): do not start it again
                raise LLMError(f"Модель не ответила за {settings.LLM_TIMEOUT_SECONDS:.0f} с") from e
            except (httpx.TransportError, httpx.TimeoutException) as e:
                last_error = LLMError(f"Сеть недоступна при обращении к модели: {e!r}")
                logger.warning("LLM %s network error (attempt %d): %r", model, attempt, e)
                await asyncio.sleep(1.5 * attempt)
                continue

            if response.status_code == 200:
                return self._parse(model, response)

            body = response.text
            message = _error_message(response.status_code, body)
            block = response.status_code == 403 and _looks_like_provider_block(body)
            unknown_model = response.status_code in (400, 404) and "model" in body.lower() and (
                "not found" in body.lower() or "not a valid" in body.lower() or "no endpoints" in body.lower()
            )
            last_error = LLMError(
                message, status=response.status_code, fallback_ok=block or unknown_model
            )
            logger.warning("LLM %s HTTP %d (attempt %d): %s", model, response.status_code, attempt, message)
            retryable = response.status_code in _RETRY_STATUSES or (block and attempt < 3)
            if not retryable:
                break
            await asyncio.sleep(1.0 * attempt)

        assert last_error is not None
        raise last_error

    async def complete_any(
        self,
        models: Sequence[str],
        messages: Sequence[Msg],
        *,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> Completion:
        """Try ``models`` in order, moving on only when another model may help."""
        last: LLMError | None = None
        for model in models:
            try:
                return await self.complete(model, messages, max_tokens=max_tokens, json_mode=json_mode)
            except LLMError as e:
                last = e
                if not e.fallback_ok:
                    raise
                logger.warning("LLM %s unavailable (%s), falling back", model, e.message)
        assert last is not None
        raise last

    @staticmethod
    def _parse(model: str, response: httpx.Response) -> Completion:
        try:
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise LLMError(f"Модель вернула неожиданный ответ: {e!r}")
        if isinstance(content, list):  # some providers return content blocks
            content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
        return Completion(
            text=content,
            model=data.get("model") or model,
            truncated=choice.get("finish_reason") == "length",
            usage=data.get("usage") or {},
        )


_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_+-]*\s*\n|\n?```\s*$")


def strip_fences(text: str) -> str:
    """Drop a markdown code fence wrapped around the whole text."""
    text = text.strip()
    if text.startswith("```"):
        text = _FENCE_RE.sub("", text).strip()
    return text


def parse_json(text: str) -> dict:
    """Parse a JSON object from model output (fences and surrounding prose tolerated)."""
    cleaned = strip_fences(text)
    try:
        value = json.loads(cleaned)
    except ValueError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise LLMError("Модель вернула не JSON")
        try:
            value = json.loads(cleaned[start:end + 1])
        except ValueError as e:
            raise LLMError(f"Модель вернула некорректный JSON: {e}")
    if not isinstance(value, dict):
        raise LLMError("Модель вернула JSON не-объект")
    return value


llm: LLM = LLMClient()
