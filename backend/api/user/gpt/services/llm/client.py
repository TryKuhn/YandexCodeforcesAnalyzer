"""Thin async LLM client over the OpenRouter chat-completions API.

This is the single low-level entry point for every AI call in the task
pipeline. Higher layers (generation/, chat/, build/) build messages and call
``ask`` / ``ask_text``; they never talk to httpx directly.
"""
import json
import logging
import re
from typing import Any, Dict, List

import httpx
from fastapi import HTTPException

from settings import settings

logger = logging.getLogger(__name__)

_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\r?\n?|```\s*$", re.MULTILINE)


def strip_code_fences(code: str) -> str:
    """Remove leading/trailing markdown code fences from a code string."""
    return _CODE_FENCE_RE.sub("", code).strip()


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
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    self.url, headers=self.headers, json=payload
                )
                if response.status_code != 200:
                    logger.error(
                        f"AI API Error: {response.status_code} - {response.text}"
                    )
                    raise HTTPException(
                        status_code=500, detail=f"AI Service error: {response.text}"
                    )

                result = response.json()
                content = result["choices"][0]["message"]["content"]

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
                    raise
            except HTTPException:
                raise
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.error(f"AI Service network error: {e}")
                raise HTTPException(
                    status_code=503, detail="AI service unavailable: network error"
                )
            except Exception as e:
                logger.error(f"AI Service Exception: {e}")
                raise HTTPException(status_code=500, detail=f"AI service error: {e}")

    async def ask_text(self, model: str, messages: List[Dict]) -> str:
        """Convenience wrapper for non-JSON calls returning the raw text."""
        result = await self.ask(model, messages, json_mode=False)
        return result.get("text", "").strip()


llm = LLMClient()
