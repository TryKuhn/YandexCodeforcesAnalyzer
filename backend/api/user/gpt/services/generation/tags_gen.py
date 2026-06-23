"""Algorithm-tag suggestion."""
import json
from typing import Dict

from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.prompts.tags import SYSTEM_PROMPT


async def suggest(statement: Dict, model: str) -> list[str]:
    """Suggest algorithm tags for the statement as a list of strings."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"},
    ]
    result = await llm.ask(model, messages)
    return [str(t) for t in result.get("tags", []) if t]
