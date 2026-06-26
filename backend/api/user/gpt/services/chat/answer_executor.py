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


# Context budget: include the ACTUAL file contents so the model can answer about
# solutions/checker/etc. The focused file gets more room; the rest are truncated.
_FOCUS_LIMIT = 6000
_PER_FILE_LIMIT = 2500
_TOTAL_LIMIT = 18000


def _build_context(statement: Dict, files: Dict, resolved: ResolvedContext) -> list[str]:
    """Build the context blocks: statement summary + the CONTENT of every file
    (focused file first and fuller), truncated to a total budget."""
    parts: list[str] = []
    if statement:
        summary = {k: v for k, v in statement.items()
                   if k in ("name", "legend", "input", "output", "scoring", "interaction")}
        parts.append(f"ЗАДАЧА: {json.dumps(summary, ensure_ascii=False)}")

    if not files:
        return parts

    focus = resolved.file_key if resolved.scope == "file" else None
    ordered = ([focus] if focus and focus in files else []) \
        + [k for k in files if k != focus]

    used = 0
    omitted: list[str] = []
    for key in ordered:
        content = (files.get(key) or "").strip()
        if not content:
            continue
        limit = _FOCUS_LIMIT if key == focus else _PER_FILE_LIMIT
        snippet = content[:limit]
        block = f"ФАЙЛ {key}:\n```\n{snippet}\n```"
        if used + len(block) > _TOTAL_LIMIT:
            omitted.append(key)
            continue
        parts.append(block)
        used += len(block)

    if omitted:
        parts.append(f"(файлы, опущенные из-за объёма: {', '.join(omitted)} — "
                     "спросите про них отдельно)")
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
