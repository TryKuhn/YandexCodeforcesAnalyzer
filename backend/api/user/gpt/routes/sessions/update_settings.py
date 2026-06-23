"""PATCH /session/{session_id}/settings — update model / system prompt."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import UpdateSessionSettingsRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.llm.models import normalize_model
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from app.database import get_db


@gpt_router.patch("/session/{session_id}/settings")
async def update_session_settings(
    session_id: str,
    request: UpdateSessionSettingsRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the session's model and/or system prompt."""
    session = await get_session_or_404(db, session_id, user_id)

    if request.model is not None:
        session.model = normalize_model(request.model)
    if request.system_prompt is not None:
        session.system_prompt = request.system_prompt

    session.updated_at = now_utc()
    await db.commit()
    return {
        "status": "ok",
        "model": session.model,
        "system_prompt": session.system_prompt,
    }
