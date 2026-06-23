"""PATCH /session/{session_id}/statement-field — edit one statement field."""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import UpdateStatementFieldRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from app.database import get_db

ALLOWED_FIELDS = {
    "scoring", "interaction", "notes", "tutorial",
    "legend", "input", "output", "name",
}


@gpt_router.patch("/session/{session_id}/statement-field")
async def update_statement_field(
    session_id: str,
    request: UpdateStatementFieldRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a single allowed field of the session's statement."""
    session = await get_session_or_404(db, session_id, user_id)
    if not session.statement:
        raise HTTPException(400, "Условие не создано")
    if request.field not in ALLOWED_FIELDS:
        raise HTTPException(
            400, f"Поле '{request.field}' не может быть изменено через этот эндпоинт"
        )

    stmt = dict(session.statement)
    stmt[request.field] = request.value
    session.statement = stmt
    session.updated_at = now_utc()
    await db.commit()
    return {"session_id": session_id, "field": request.field, "value": request.value}
