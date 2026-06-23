"""Cheap intent-router agent: classifies a chat message into one concrete action.

A single small router model decides what the user wants (ask / edit statement /
edit file / edit tests / build / regenerate / multi-file edit) instead of keyword
heuristics. It defaults to ``answer`` on any error so a router hiccup never makes
the chat destructive.
"""
from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.llm.models import ROUTER_MODEL
from api.user.gpt.services.prompts import intent as intent_prompt


async def classify_action(
    message: str, context_hint: str, available_files: list[str]
) -> dict:
    """Classify a message into one concrete action via the cheap router model.

    Returns {"action": str, "file_key": str | None}. Falls back to ``answer`` on
    any error and drops a file_key that is not actually present. An
    ``edit_file`` without a valid target is demoted to ``edit_task`` so the
    multi-file editor decides which file to touch.
    """
    fallback = {"action": "answer", "file_key": None}
    try:
        result = await llm.ask(
            ROUTER_MODEL,
            [
                {"role": "system", "content": intent_prompt.SYSTEM_PROMPT},
                {"role": "user",
                 "content": intent_prompt.build_user_prompt(
                     message, context_hint, available_files)},
            ],
            json_mode=True,
        )
    except Exception:
        return fallback

    action = result.get("action")
    if action not in intent_prompt.ACTIONS:
        return fallback

    file_key = result.get("file_key")
    if file_key and file_key not in available_files:
        file_key = None
    if action == "edit_file" and not file_key:
        action = "edit_task"
    return {"action": action, "file_key": file_key}
