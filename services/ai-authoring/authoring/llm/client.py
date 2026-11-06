"""Async LLM client: OpenRouter by default, the vendors' own APIs with a user's own key.

* transient failures (429, 5xx, network) are retried with back-off;
* a provider refusal (403 "not allowed" / region block) is retried a couple of
  times -- OpenRouter routes every request independently, so a retry may land
  on an allowed provider -- and then reported as ``fallback_ok`` so
  :meth:`LLMClient.complete_any` moves on to the next model;
* Anthropic models get ``cache_control`` on the blocks marked cacheable (the
  problem materials), which makes repeated calls over the same problem cheap;
* with a user's :class:`Credentials` (:func:`route_for`): an Anthropic key sends
  anthropic/* models to the Anthropic Messages API, an OpenAI key sends openai/*
  models to the OpenAI API, an OpenRouter key replaces ours for the rest. A
  rejected own key is an error with a clear message -- never a silent fallback
  to the server's key.
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

from authoring.llm.models import DIRECT_MODEL_IDS, is_anthropic, is_openai
from authoring.settings import settings

logger = logging.getLogger(__name__)

# 529: Anthropic "overloaded"
_RETRY_STATUSES = {429, 500, 502, 503, 504, 529}
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


@dataclass(frozen=True)
class Credentials:
    """The user's own API keys (profile -> "ИИ-модели"); all optional."""

    openrouter: str | None = None
    anthropic: str | None = None
    openai: str | None = None


PROVIDER_NAMES = {"openrouter": "OpenRouter", "anthropic": "Anthropic", "openai": "OpenAI"}


@dataclass(frozen=True)
class Route:
    """Where one request goes: the provider, its key and the model id it understands."""

    provider: str  # openrouter | anthropic | openai
    key: str
    model: str
    own_key: bool  # the user's key (errors are reported as such, never silently replaced)

    @property
    def name(self) -> str:
        return PROVIDER_NAMES[self.provider]


def route_for(model: str, credentials: Credentials | None) -> Route:
    """The user's vendor key for that vendor's models, then the user's OpenRouter key, then ours."""
    creds = credentials or Credentials()
    direct = DIRECT_MODEL_IDS.get(model)
    if direct and creds.anthropic and is_anthropic(model):
        return Route("anthropic", creds.anthropic, direct, own_key=True)
    if direct and creds.openai and is_openai(model):
        return Route("openai", creds.openai, direct, own_key=True)
    if creds.openrouter:
        return Route("openrouter", creds.openrouter, model, own_key=True)
    return Route("openrouter", settings.OPENAI_API_KEY, model, own_key=False)


_JSON_ONLY = "Ответ -- строго один JSON-объект, без пояснений и без ```."
# Anthropic allows at most 4 cache breakpoints per request
_MAX_CACHE_BREAKPOINTS = 4


def render_anthropic(messages: Sequence[Msg], *, json_mode: bool = False) -> tuple[list[dict], list[dict]]:
    """Native Messages API: (system blocks, messages); same-role neighbours are merged."""
    system: list[dict[str, Any]] = []
    turns: list[dict[str, Any]] = []
    breakpoints = 0
    for msg in messages:
        blocks: list[dict[str, Any]] = []
        for part in msg.parts:
            if not part.text.strip():
                continue  # empty text blocks are rejected
            block: dict[str, Any] = {"type": "text", "text": part.text}
            if part.cache and breakpoints < _MAX_CACHE_BREAKPOINTS:
                block["cache_control"] = {"type": "ephemeral"}
                breakpoints += 1
            blocks.append(block)
        if not blocks:
            continue
        if msg.role == "system":
            system.extend(blocks)
        elif turns and turns[-1]["role"] == msg.role:
            turns[-1]["content"].extend(blocks)
        else:
            turns.append({"role": msg.role, "content": blocks})
    if json_mode:
        system.append({"type": "text", "text": _JSON_ONLY})
    return system, turns


class LLMClient:
    """OpenRouter client (and, with a user's own keys, the Anthropic / OpenAI APIs).

    The shared instance (``llm``) uses the server's OpenRouter key; a per-user
    instance gets that user's :class:`Credentials` (see :mod:`authoring.llm.credentials`).
    """

    def __init__(
        self, transport: httpx.AsyncBaseTransport | None = None, *, credentials: Credentials | None = None
    ) -> None:
        base = settings.OPENAI_HOST.rstrip("/")
        self.url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        self._transport = transport
        self.credentials = credentials

    def _request(
        self, route: Route, messages: Sequence[Msg], max_tokens: int, json_mode: bool, original_model: str
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        """(url, headers, payload) for ``route``."""
        if route.provider == "anthropic":
            system, turns = render_anthropic(messages, json_mode=json_mode)
            payload: dict[str, Any] = {"model": route.model, "max_tokens": max_tokens, "messages": turns}
            if system:
                payload["system"] = system
            headers = {
                "x-api-key": route.key,
                "anthropic-version": settings.ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            }
            return settings.ANTHROPIC_API_URL, headers, payload
        if route.provider == "openai":
            payload = {
                "model": route.model,
                "messages": render_messages(original_model, messages),
                # reasoning models take max_completion_tokens (max_tokens is deprecated)
                "max_completion_tokens": max_tokens,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            headers = {"Authorization": f"Bearer {route.key}", "Content-Type": "application/json"}
            return settings.OPENAI_DIRECT_URL, headers, payload
        payload = {
            "model": route.model,
            "messages": render_messages(original_model, messages),
            # always capped: OpenRouter reserves max_tokens in its affordability check
            "max_tokens": max_tokens,
            "usage": {"include": True},
        }
        if settings.openrouter_provider:
            payload["provider"] = settings.openrouter_provider
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {route.key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://createmanager.duckdns.org",
            "X-Title": "Createmanager AI authoring",
        }
        return self.url, headers, payload

    async def complete(
        self,
        model: str,
        messages: Sequence[Msg],
        *,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> Completion:
        route = route_for(model, self.credentials)
        url, headers, payload = self._request(
            route, messages, max_tokens or settings.LLM_MAX_TOKENS, json_mode, model
        )

        last_error: LLMError | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=settings.LLM_TIMEOUT_SECONDS, transport=self._transport
                ) as http:
                    response = await http.post(url, headers=headers, json=payload)
            except httpx.ReadTimeout as e:
                # the model may still be generating (and billing): do not start it again
                raise LLMError(f"Модель не ответила за {settings.LLM_TIMEOUT_SECONDS:.0f} с") from e
            except (httpx.TransportError, httpx.TimeoutException) as e:
                last_error = LLMError(f"Сеть недоступна при обращении к модели: {e!r}")
                logger.warning("LLM %s network error (attempt %d): %r", model, attempt, e)
                await asyncio.sleep(1.5 * attempt)
                continue

            if response.status_code == 200:
                try:
                    if route.provider == "anthropic":
                        return self._parse_anthropic(model, response)
                    return self._parse(model, response)
                except LLMError as e:
                    if e.status != 502:
                        raise
                    last_error = e
                    logger.warning("LLM %s bad 200 answer (attempt %d): %s", model, attempt, e.message)
                    await asyncio.sleep(1.0 * attempt)
                    continue

            body = response.text
            last_error = _http_error(route, response.status_code, body)
            logger.warning(
                "LLM %s via %s%s HTTP %d (attempt %d): %s", model, route.name,
                " (own key)" if route.own_key else "", response.status_code, attempt, last_error.message,
            )
            block = route.provider == "openrouter" and response.status_code == 403 \
                and _looks_like_provider_block(body)
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
        finish = choice.get("finish_reason")
        # OpenRouter reports a provider failure mid-generation as HTTP 200 with an
        # error inside the choice (finish_reason "error") and an empty/partial text
        error = choice.get("error") if isinstance(choice, dict) else None
        if error or finish == "error":
            detail = error.get("message") if isinstance(error, dict) else error
            raise LLMError(f"Провайдер модели оборвал ответ: {detail or 'ошибка генерации'}", status=502)
        if not str(content).strip() and finish != "length":
            raise LLMError("Модель вернула пустой ответ", status=502)
        return Completion(
            text=content,
            model=data.get("model") or model,
            truncated=finish == "length",
            usage=data.get("usage") or {},
        )

    @staticmethod
    def _parse_anthropic(model: str, response: httpx.Response) -> Completion:
        """Messages API answer: text blocks joined (thinking blocks are skipped)."""
        try:
            data = response.json()
            blocks = data["content"]
        except (ValueError, KeyError, TypeError) as e:
            raise LLMError(f"Модель вернула неожиданный ответ: {e!r}")
        text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
        stop = data.get("stop_reason")
        details = data.get("stop_details") or {}
        if not text.strip() and (stop == "refusal" or details.get("type") == "refusal"):
            raise LLMError(f"Модель отказалась отвечать: {details.get('explanation') or 'без пояснений'}")
        if not text.strip() and stop != "max_tokens":
            raise LLMError("Модель вернула пустой ответ", status=502)
        return Completion(
            text=text,
            model=data.get("model") or model,
            truncated=stop == "max_tokens",
            usage=data.get("usage") or {},
        )


def _http_error(route: Route, status: int, body: str) -> LLMError:
    """A non-200 answer as an LLMError; problems with the user's own key say so."""
    if not route.own_key:
        message = _error_message(status, body)
        unknown_model = status in (400, 404) and "model" in body.lower() and (
            "not found" in body.lower() or "not a valid" in body.lower() or "no endpoints" in body.lower()
        )
        block = status == 403 and _looks_like_provider_block(body)
        return LLMError(message, status=status, fallback_ok=block or unknown_model)

    detail = _raw_error(body) or f"HTTP {status}"
    low = detail.lower()
    if status in (401, 403) and not _looks_like_provider_block(low):
        return LLMError(f"Ваш ключ {route.name} отклонён: {detail}", status=status)
    if status == 402 or "credit" in low or "billing" in low or "quota" in low:
        return LLMError(f"На балансе вашего ключа {route.name} недостаточно средств: {detail}", status=status)
    if status == 403:
        return LLMError(f"{route.name} отклонил запрос с вашим ключом (возможно, региональная блокировка): "
                        f"{detail}", status=status)
    unknown_model = status in (400, 404) and "model" in low and ("not found" in low or "not_found" in low
                                                                 or "does not exist" in low)
    return LLMError(f"{route.name} (ваш ключ): {detail}", status=status, fallback_ok=unknown_model)


def _raw_error(body: str) -> str:
    """The error message of an OpenRouter / Anthropic / OpenAI error body."""
    try:
        data = json.loads(body)
        err = data.get("error", data) if isinstance(data, dict) else {}
        message = err.get("message") if isinstance(err, dict) else str(err)
        raw = (err.get("metadata") or {}).get("raw") if isinstance(err, dict) else None
        if isinstance(raw, str) and raw:
            try:
                message = json.loads(raw).get("error", {}).get("message") or message
            except (ValueError, AttributeError):
                message = raw
        return str(message or "")[:400]
    except (ValueError, AttributeError, TypeError):
        return body[:400]


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
