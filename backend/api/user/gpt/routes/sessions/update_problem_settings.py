"""PATCH /session/{session_id}/problem-settings — update TL/ML/IO/tags/groups."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import UpdateProblemSettingsRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from app.database import get_db


@gpt_router.patch("/session/{session_id}/problem-settings")
async def update_problem_settings(
    session_id: str,
    request: UpdateProblemSettingsRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Merge new TL/ML/IO/tags/groups into the session's problem_settings.

    Reassigns a fresh dict because in-place mutation of a JSON column is not
    tracked by SQLAlchemy; flag_modified marks it dirty for the commit.
    """
    session = await get_session_or_404(db, session_id, user_id)
    session.problem_settings = {
        **(session.problem_settings or {}),
        **request.settings.model_dump(exclude_none=False),
    }
    flag_modified(session, "problem_settings")
    session.updated_at = now_utc()
    await db.commit()
    return {"session_id": session_id, "problem_settings": session.problem_settings}
