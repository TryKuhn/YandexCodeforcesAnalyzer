"""Interaction statement-section text generation (interactive problems)."""
import json
from typing import Dict

from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.prompts.interaction import SYSTEM_PROMPT


async def generate(statement: Dict, model: str) -> str:
    """Generate the Interaction statement-section text for an interactive problem."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"},
    ]
    return await llm.ask_text(model, messages)
