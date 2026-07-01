"""Thin async LLM client over the OpenRouter chat-completions API.

This is the single low-level entry point for every AI call in the task
pipeline. Higher layers (generation/, chat/, build/) build messages and call
``ask`` / ``ask_text``; they never talk to httpx directly.
"""
import asyncio
import json
import logging
import re
from typing import Any, Dict, List

import httpx
from fastapi import HTTPException

from settings import settings

logger = logging.getLogger(__name__)

_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\r?\n?|```\s*$", re.MULTILINE)

# OpenRouter / upstream providers occasionally return transient gateway errors
# (502/503/504) or drop the connection — retry those a few times with backoff so
# a blip doesn't kill a long generation/auto-repair run.
_RETRY_STATUSES = {502, 503, 504}
# A 403 "Request not allowed" / region block is NOT deterministic on OpenRouter:
# a model (e.g. claude-haiku-4.5) may have several providers, only SOME of which
# geo-block the account's region. Each request is routed independently, so a
# retry can land on an allowed provider. Retrying such a 403 makes an
# intermittently-blocked model usable (crucial for heavy multi-call generation,
# where one blocked call would otherwise abort the whole task).
_MAX_RETRIES = 4


def strip_code_fences(code: str) -> str:
    """Remove leading/trailing markdown code fences from a code string."""
    return _CODE_FENCE_RE.sub("", code).strip()


def _looks_like_provider_block(text: str) -> bool:
    """True when a 403 body looks like a provider/region block (not a hard auth error)."""
    low = (text or "").lower()
    return any(k in low for k in
               ("not allowed", "region", "country", "territory", "unsupported_country"))


def _friendly_error(status: int, text: str) -> str:
    """Turn a raw OpenRouter error body into a short, human-readable RU message.

    OpenRouter dumps a nested JSON blob (``error.message``, ``error.metadata.raw``)
    that is noisy and confusing in the chat. We surface the common, actionable
    cases explicitly and fall back to the upstream message otherwise.
    """
    message = text
    try:
        body = json.loads(text)
        err = body.get("error", body) if isinstance(body, dict) else {}
        message = err.get("message") or message
        raw = (err.get("metadata") or {}).get("raw")
        if raw:
            try:
                message = json.loads(raw).get("error", {}).get("message") or message
            except (json.JSONDecodeError, AttributeError, TypeError):
                message = raw if isinstance(raw, str) else message
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    low = (message or "").lower()
    if status == 402 or "credit" in low or "afford" in low:
        return ("Недостаточно средств на балансе OpenRouter для этого запроса. "
                "Пополните баланс или выберите другую модель.")
    if status == 403 and _looks_like_provider_block(low):
        return ("Провайдер модели отклонил запрос (часто это региональная "
                "блокировка). Обычно помогает повтор — попробуйте ещё раз или "
                "выберите другую модель.")
    return message[:400] if message else f"Ошибка LLM (HTTP {status})"


class LLMClient:
    """Stateless client; safe to instantiate per request or reuse as a module global."""

    def __init__(self) -> None:
        self.api_key = settings.OPENAI_API_KEY
        base_url = settings.OPENAI_HOST.rstrip("/")
        self.url = (
            f"{base_url}/chat/completions"
            if not base_url.endswith("/chat/completions")
            else base_url
        )
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://judge-system.com",
            "X-Title": "Judge System AI",
        }

    async def ask(
        self, model: str, messages: List[Dict], json_mode: bool = True
    ) -> Dict:
        """Call the model. With json_mode=True returns the parsed JSON dict;
        with json_mode=False returns {"text": <raw assistant text>}."""
        payload: Dict[str, Any] = {"model": model, "messages": messages}
        # Always cap output tokens: without this OpenRouter reserves the model's
        # full max output (e.g. 65536 for gpt-5.5-pro) for its pre-flight
        # affordability check and returns 402 when the balance can't cover it.
        if settings.LLM_MAX_TOKENS:
            payload["max_tokens"] = settings.LLM_MAX_TOKENS
        # Provider routing lets a region-blocked model (e.g. gpt-5.5-pro via
        # OpenAI-direct) route to an allowed provider; empty when unconfigured.
        provider = settings.openrouter_provider
        if provider:
            payload["provider"] = provider
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        for attempt in range(_MAX_RETRIES):
            last = attempt == _MAX_RETRIES - 1
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        self.url, headers=self.headers, json=payload
                    )
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.warning(f"AI network error ({e!r}), attempt {attempt + 1}/{_MAX_RETRIES}")
                if last:
                    raise HTTPException(
                        status_code=503, detail="AI service unavailable: network error"
                    )
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            except Exception as e:
                logger.error(f"AI Service Exception: {e}")
                raise HTTPException(status_code=500, detail=f"AI service error: {e}")

            if response.status_code != 200:
                logger.error(f"AI API Error: {response.status_code} - {response.text[:300]}")
                retryable = response.status_code in _RETRY_STATUSES or (
                    response.status_code == 403
                    and _looks_like_provider_block(response.text)
                )
                if retryable and not last:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                raise HTTPException(
                    status_code=502,
                    detail=_friendly_error(response.status_code, response.text),
                )

            try:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"AI Service bad response: {e}")
                raise HTTPException(status_code=500, detail=f"AI service error: {e}")

            if not json_mode:
                return {"text": content}

            content = content.strip()
            content = re.sub(
                r"^```(?:json)?\n?|```$", "", content, flags=re.MULTILINE
            ).strip()
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    return json.loads(match.group())
                raise HTTPException(status_code=500, detail="AI returned non-JSON output")

        raise HTTPException(status_code=503, detail="AI service unavailable")  # unreachable

    async def ask_text(self, model: str, messages: List[Dict]) -> str:
        """Convenience wrapper for non-JSON calls returning the raw text."""
        result = await self.ask(model, messages, json_mode=False)
        return result.get("text", "").strip()


llm = LLMClient()
