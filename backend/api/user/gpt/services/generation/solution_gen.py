"""Generate a solution file for an arbitrary tag (used by custom solutions).

The registry-driven path (``file_gen``) covers the fixed solution slots; this
module handles a custom solution whose tag/name come from ``solution_meta``.
"""
import json
from typing import Dict

from api.user.gpt.services.llm.client import llm, strip_code_fences
from api.user.gpt.services.prompts.base import ASCII_CODE_RULE
from api.user.gpt.services.prompts.solution import build_system_prompt


async def generate_for_tag(
    tag: str, name: str, statement: Dict, model: str,
    instruction: str | None = None,
) -> str:
    """Generate solution code for a given Polygon tag (MA/OK/WA/TL/RE/ML/...).

    ``instruction`` is an optional free-form user note (e.g. "сделай на Python",
    "решение перебором O(n^2)") that steers the generation.
    """
    user_parts = [
        f"Имя файла: {name}",
        f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}",
    ]
    if instruction and instruction.strip():
        user_parts.append(f"Дополнительные пожелания к решению: {instruction.strip()}")
    messages = [
        {"role": "system", "content": build_system_prompt(tag) + "\n" + ASCII_CODE_RULE},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
    return strip_code_fences(await llm.ask_text(model, messages))
