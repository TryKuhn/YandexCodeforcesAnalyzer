"""POST /chat — AI chat with LLM intent routing.

1. Persist the user message immediately (survives a crash).
2. A cheap router model classifies the message into ONE action:
   answer / edit_statement / edit_file / edit_test / edit_task / build / regenerate.
3. Dispatch to the matching executor.
4. Persist the assistant message and return a ChatResponse.

Modify pushes changes to Polygon immediately; a build runs in the background.
"""
import asyncio
import logging
from typing import Literal

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import ChatRequest, ChatResponse
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.ai_file_helpers import get_all_file_contents
from api.user.gpt.services.build.repair import run_build_with_repair
from api.user.gpt.services.chat import (answer_executor, context_resolver,
                                        intent_router, modify_executor)
from api.user.gpt.services.chat.context_resolver import ResolvedContext
from api.user.gpt.services.chat.file_context import ensure_files_loaded
from api.user.gpt.services.sessions import (append_chat_log, chat_message,
                                            get_session_or_404)
from api.user.polygon.get_response import PolygonAPIError
from app.database import get_db

logger = logging.getLogger(__name__)


def _error_text(e: Exception) -> str:
    """Extract a human-readable message from any exception type."""
    if isinstance(e, HTTPException):
        return str(e.detail)
    if isinstance(e, PolygonAPIError):
        return e.message
    return str(e) or e.__class__.__name__


def _context_hint(ctx) -> str:
    """Describe the user's current context scope for the intent router."""
    if ctx.scope == "file":
        return f"the file '{ctx.file_key}'" if ctx.file_key else "a source file"
    if ctx.scope == "statement":
        return "the problem statement"
    return "the whole task"


def _resolved_for(action: str, file_key: str | None,
                  available_files: list[str]) -> ResolvedContext:
    """Map an edit action to the ResolvedContext the modify executor expects.

    For ``edit_test`` the edit targets the FreeMarker generation script, since
    tests are produced by that script rather than edited directly.
    """
    if action == "edit_statement":
        return ResolvedContext(scope="statement")
    if action == "edit_file" and file_key:
        return ResolvedContext(scope="file", file_key=file_key, candidates=[file_key])
    if action == "edit_test":
        if "script" in available_files:
            return ResolvedContext(scope="file", file_key="script", candidates=["script"])
        if file_key:
            return ResolvedContext(scope="file", file_key=file_key, candidates=[file_key])
    return ResolvedContext(scope="task", candidates=available_files)


@gpt_router.post("/chat", response_model=ChatResponse)
async def unified_chat(
    request: ChatRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Route a chat message to one executor and persist both sides of the turn.

    The user message is persisted before routing so it survives a crash; an
    explicitly-viewed file is honoured when the router leaves the file unset.
    A full task/pack (re)generation triggers a background package build with
    auto-repair, whereas a plain single-file edit does not.
    """
    session = await get_session_or_404(db, request.session_id, user_id)
    await ensure_files_loaded(db, session)

    # Conversation so far (BEFORE this turn) — fed to the answer model as
    # history. The chat flow persists turns to chat_log, so that — not the
    # rarely-populated session.history column — is the real transcript.
    prior_log = list(session.chat_log or [])

    await append_chat_log(db, session.id, [
        chat_message("user", request.message, context=request.context.model_dump()),
    ])

    available_files = list((await get_all_file_contents(db, session.id)).keys())

    intent = await intent_router.classify_action(
        request.message, _context_hint(request.context), available_files,
        main_model=session.model,
    )
    action = intent["action"]
    file_key = intent["file_key"]
    if not file_key and request.context.scope == "file":
        file_key = request.context.file_key

    if action == "build":
        if not session.polygon_problem_id:
            text, err = "❌ Задача ещё не создана в Polygon.", True
        else:
            asyncio.create_task(run_build_with_repair(session.id))
            text, err = ("🔨 Запустил сборку пакета с авто-починкой. "
                         "Прогресс — на вкладке «Пакеты».", False)
        await append_chat_log(db, session.id, [
            chat_message("assistant", text, action="answer",
                         context=request.context.model_dump(), is_error=err),
        ])
        return ChatResponse(action="answer", response=text, is_error=err)

    updated_files: list[str] = []
    statement = None
    technical_data = None
    synced = False
    is_error = False
    resp_action: Literal["answer", "modify"] = (
        "answer" if action == "answer" else "modify"
    )

    try:
        if action == "answer":
            resolved = await context_resolver.resolve(db, session, request.context)
            files = await get_all_file_contents(db, session.id)
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in prior_log
                if m.get("role") in ("user", "assistant") and m.get("content")
            ]
            response_text = await answer_executor.execute(
                message=request.message,
                statement=session.statement or {},
                files=files,
                model=session.model,
                history=history,
                resolved=resolved,
                problem_type=session.problem_type,
            )
        else:
            if action == "regenerate":
                result = await modify_executor.regenerate(db, session, request.message)
            else:
                resolved = _resolved_for(action, file_key, available_files)
                result = await modify_executor.execute(
                    db, session, request.message, resolved
                )
            response_text = result["response"]
            updated_files = result["updated_files"]
            statement = result["statement"]
            technical_data = result["technical_data"]
            synced = result["synced"]
            if result.get("build") and session.polygon_problem_id:
                asyncio.create_task(run_build_with_repair(session.id))
                response_text += ("\n\n🔨 Запустил сборку пакета с авто-починкой — "
                                  "прогресс на вкладке «Пакеты».")
    except Exception as e:
        logger.exception(f"[{session.id}] chat executor failed: {e}")
        is_error = True
        response_text = f"❌ Ошибка: {_error_text(e)}"

    await append_chat_log(db, session.id, [
        chat_message("assistant", response_text, action=resp_action,
                     context=request.context.model_dump(),
                     updated_files=updated_files, is_error=is_error),
    ])

    return ChatResponse(
        action=resp_action,
        response=response_text,
        updated_files=updated_files,
        synced_to_polygon=synced,
        statement=statement,
        technical_data=technical_data,
        is_error=is_error,
    )
