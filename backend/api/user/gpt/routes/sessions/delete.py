"""DELETE /session/{session_id} — delete a session and its generated files."""
from fastapi import Depends
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.sessions import get_session_or_404
from app.database import get_db
from models.task.generated_file import TaskGeneratedFile


@gpt_router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete the session and its generated technical files."""
    session = await get_session_or_404(db, session_id, user_id)
    await db.execute(
        delete(TaskGeneratedFile).where(TaskGeneratedFile.session_id == session_id)
    )
    await db.delete(session)
    await db.commit()
    return {"status": "deleted"}
