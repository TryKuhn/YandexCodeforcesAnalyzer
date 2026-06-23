"""Generate a solution file for an arbitrary tag (used by custom solutions).

The registry-driven path (``file_gen``) covers the fixed solution slots; this
module handles a custom solution whose tag/name come from ``solution_meta``.
"""
import json
from typing import Dict

from api.user.gpt.services.llm.client import llm, strip_code_fences
from api.user.gpt.services.prompts.base import ASCII_CODE_RULE
from api.user.gpt.services.prompts.solution import build_system_prompt


async def generate_for_tag(tag: str, name: str, statement: Dict, model: str) -> str:
    """Generate solution code for a given Polygon tag (MA/OK/WA/TL/RE/ML/...)."""
    messages = [
        {"role": "system", "content": build_system_prompt(tag) + "\n" + ASCII_CODE_RULE},
        {
            "role": "user",
            "content": (
                f"Имя файла: {name}\n"
                f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"
            ),
        },
    ]
    return strip_code_fences(await llm.ask_text(model, messages))
