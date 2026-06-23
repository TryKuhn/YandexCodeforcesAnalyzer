"""Sample-test generation for the statement."""
import json
from typing import Dict

from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.prompts.samples import build_system_prompt


async def generate(statement: Dict, model: str, count: int = 3) -> list[dict]:
    """Generate up to ``count`` sample tests as [{input, output}] for the statement."""
    messages = [
        {"role": "system", "content": build_system_prompt(count)},
        {"role": "user", "content": f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"},
    ]
    result = await llm.ask(model, messages)
    return [
        {"input": str(e.get("input", "")), "output": str(e.get("output", ""))}
        for e in result.get("examples", [])
    ]
