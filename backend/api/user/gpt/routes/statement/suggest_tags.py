"""POST /suggest-tags — AI tag suggestions from the statement."""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import SuggestTagsRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.chat.file_context import ensure_files_loaded
from api.user.gpt.services.generation import tags_gen
from api.user.gpt.services.sessions import get_session_or_404
from app.database import get_db


@gpt_router.post("/suggest-tags")
async def suggest_tags(
    request: SuggestTagsRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Suggest tags for the session's statement.

    Pulls the statement from Polygon for tab-opened sessions via
    ensure_files_loaded before checking that a statement exists.
    """
    session = await get_session_or_404(db, request.session_id, user_id)
    await ensure_files_loaded(db, session)
    if not session.statement:
        raise HTTPException(400, "Условие ещё не создано")

    tags = await tags_gen.suggest(session.statement, session.model)
    return {"session_id": session.id, "suggested_tags": tags}
