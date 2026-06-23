"""Statement generation / refinement."""
from typing import Dict, List

from fastapi import HTTPException

from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.prompts import problem_type as problem_type_guide
from api.user.gpt.services.prompts.statement import SYSTEM_PROMPT

MAX_IDEA_CHARS = 50_000


async def generate(
    user_idea: str, model: str, user_prompt: str | None, history: List[Dict],
    problem_type=None,
) -> Dict:
    """Generate or iterate the statement JSON {name, legend, input, output, notes, tutorial}."""
    if len(user_idea) > MAX_IDEA_CHARS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Текст слишком длинный ({len(user_idea)} символов). "
                f"Максимум — {MAX_IDEA_CHARS} символов."
            ),
        )
    system = user_prompt or SYSTEM_PROMPT
    if problem_type is not None:
        system = f"{problem_type_guide.guide(problem_type)}\n\n{system}"
    messages = [{"role": "system", "content": system}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": user_idea})
    return await llm.ask(model, messages, json_mode=True)
