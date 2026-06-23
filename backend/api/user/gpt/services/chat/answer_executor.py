"""Execute an 'answer' intent: reply in text, never modify.

Builds context from the session (statement summary + the file in focus, or the
file list) and answers on the user's main model. Off-topic questions are
declined by the answer prompt.
"""
import json
from typing import Dict, List

from api.user.gpt.services.chat.context_resolver import ResolvedContext
from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.prompts import problem_type as problem_type_guide
from api.user.gpt.services.prompts.answer import SYSTEM_PROMPT


def _build_context(statement: Dict, files: Dict, resolved: ResolvedContext) -> list[str]:
    """Build the context blocks (statement summary + focused file or file list)."""
    parts: list[str] = []
    if statement:
        summary = {k: v for k, v in statement.items()
                   if k in ("name", "legend", "input", "output")}
        parts.append(f"ЗАДАЧА: {json.dumps(summary, ensure_ascii=False)}")

    if resolved.scope == "file" and resolved.file_key in files:
        parts.append(f"ФАЙЛ ({resolved.file_key}):\n```\n{files[resolved.file_key][:3000]}\n```")
    elif files:
        parts.append(f"Доступные файлы: {', '.join(files.keys())}")
    return parts


async def execute(
    message: str,
    statement: Dict,
    files: Dict,
    model: str,
    history: List[Dict],
    resolved: ResolvedContext,
    problem_type=None,
) -> str:
    """Answer the user's message in text on their main model; never modifies."""
    ctx_parts = _build_context(statement or {}, files or {}, resolved)

    system = SYSTEM_PROMPT
    if problem_type is not None:
        system = f"{problem_type_guide.guide(problem_type)}\n\n{system}"
    msgs: List[Dict] = [{"role": "system", "content": system}]
    for h in (history or [])[-6:]:
        if isinstance(h, dict) and h.get("role") in ("user", "assistant"):
            msgs.append(h)

    user_content = (
        "\n\n".join(ctx_parts) + f"\n\nВОПРОС: {message}" if ctx_parts else message
    )
    msgs.append({"role": "user", "content": user_content})

    text = await llm.ask_text(model, msgs)
    return text or "Не удалось получить ответ."
