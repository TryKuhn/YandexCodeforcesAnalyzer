import json
import httpx
import logging
import re
from typing import List, Dict
from fastapi import HTTPException

from settings import settings

logger = logging.getLogger(__name__)


class TaskAIService:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        base_url = settings.OPENAI_HOST.rstrip('/')
        self.url = f"{base_url}/chat/completions" if not base_url.endswith('/chat/completions') else base_url

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://judge-system.com",
            "X-Title": "Judge System AI"
        }

    async def _base_ask(self, model: str, messages: List[Dict], json_mode: bool = True) -> Dict:
        payload = {
            "model": model,
            "messages": messages,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(self.url, headers=self.headers, json=payload)
                if response.status_code != 200:
                    logger.error(f"AI API Error: {response.status_code} - {response.text}")
                    raise HTTPException(status_code=500, detail=f"AI Service error: {response.text}")

                result = response.json()
                content = result['choices'][0]['message']['content']

                if json_mode:
                    content = content.strip()
                    content = re.sub(r'^```(?:json)?\n?|```$', '', content, flags=re.MULTILINE).strip()
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        match = re.search(r'\{.*\}', content, re.DOTALL)
                        if match:
                            return json.loads(match.group())
                        raise
                else:
                    return {"text": content}
            except Exception as e:
                logger.error(f"AI Service Exception: {str(e)}")
                raise

    async def generate_statement(self, user_idea: str, history: List[Dict] = None) -> Dict:
        system_prompt = (
            "You are a competitive programming task author. Output JSON strictly. "
            "Format: {name, legend, input, output, notes, tutorial}. Use LaTeX for formulas."
        )
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend([{"role": m["role"], "content": m["content"]} for m in history])
        messages.append({"role": "user", "content": user_idea})

        return await self._base_ask("openai/gpt-4o", messages)

    async def generate_technical_stuff(self, approved_statement: Dict) -> Dict:
        model_id = "anthropic/claude-opus-4.7"

        system_prompt = (
            "You are a testlib.h expert. Based on the problem statement, write: "
            "validator.cpp, generator.cpp, checker.cpp, solution.cpp, solution.py, and Freemarker script (script.txt). "
            "Output JSON with fields: validator, generator, checker, solution_cpp, solution_py, script."
        )
        user_prompt = f"Problem Statement:\n{json.dumps(approved_statement, ensure_ascii=False)}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return await self._base_ask(model_id, messages)

    async def fix_code(self, error: str, component: str, code: str, statement: Dict) -> str:
        model_id = "anthropic/claude-opus-4.7"
        system_prompt = f"Fix the {component} code for Polygon. Error: {error}. Return only the corrected code, no explanations."
        user_prompt = f"Statement:\n{json.dumps(statement, ensure_ascii=False)}\n\nBroken code:\n{code}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        result = await self._base_ask(model_id, messages, json_mode=False)
        return result["text"].strip()
