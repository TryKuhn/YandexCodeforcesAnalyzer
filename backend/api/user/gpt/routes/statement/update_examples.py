"""PATCH /session/{session_id}/examples — overwrite the sample tests."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import UpdateExamplesRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from app.database import get_db


@gpt_router.patch("/session/{session_id}/examples")
async def update_examples(
    session_id: str,
    request: UpdateExamplesRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Overwrite the session's sample tests with the provided examples."""
    session = await get_session_or_404(db, session_id, user_id)
    session.examples = list(request.examples)
    flag_modified(session, "examples")
    session.updated_at = now_utc()
    await db.commit()
    return {"session_id": session_id, "examples": session.examples}
