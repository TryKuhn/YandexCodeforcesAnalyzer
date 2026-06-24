"""Cheap intent-router agent: classifies a chat message into one concrete action.

A single small router model decides what the user wants (ask / edit statement /
edit file / edit tests / build / regenerate / multi-file edit) instead of keyword
heuristics. It defaults to ``answer`` on any error so a router hiccup never makes
the chat destructive — but it first retries on the main model, because a silent
fall-through to ``answer`` would route a "build me a task" request into a plain
text reply instead of the generation pipeline.
"""
import logging

from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.llm.models import ROUTER_MODEL
from api.user.gpt.services.prompts import intent as intent_prompt

logger = logging.getLogger(__name__)


async def _ask_router(model: str, message: str, context_hint: str,
                      available_files: list[str]) -> dict | None:
    """Run the classifier on one model. Returns the parsed dict or None on error."""
    try:
        return await llm.ask(
            model,
            [
                {"role": "system", "content": intent_prompt.SYSTEM_PROMPT},
                {"role": "user",
                 "content": intent_prompt.build_user_prompt(
                     message, context_hint, available_files)},
            ],
            json_mode=True,
        )
    except Exception as e:
        logger.warning(f"intent router failed on model '{model}': {e}")
        return None


async def classify_action(
    message: str, context_hint: str, available_files: list[str],
    main_model: str | None = None,
) -> dict:
    """Classify a message into one concrete action via the cheap router model.

    Returns {"action": str, "file_key": str | None}. If the cheap router model
    errors (e.g. unavailable on this account), retries on ``main_model`` — which
    is known to work since the main agent uses it — before degrading to
    ``answer``. Drops a file_key that is not actually present; an ``edit_file``
    without a valid target is demoted to ``edit_task``.
    """
    fallback = {"action": "answer", "file_key": None}

    result = await _ask_router(ROUTER_MODEL, message, context_hint, available_files)
    if result is None and main_model and main_model != ROUTER_MODEL:
        logger.info(f"intent router retrying on main model '{main_model}'")
        result = await _ask_router(main_model, message, context_hint, available_files)
    if result is None:
        logger.warning("intent router degraded to 'answer' (all models failed)")
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
