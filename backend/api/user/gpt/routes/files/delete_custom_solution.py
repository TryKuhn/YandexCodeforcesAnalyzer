"""DELETE /session/{session_id}/solution/{file_type} — remove a custom solution."""
from fastapi import Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.crypt import get_current_user
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from app.database import get_db
from models.task.generated_file import TaskGeneratedFile


@gpt_router.delete("/session/{session_id}/solution/{file_type}")
async def delete_custom_solution(
    session_id: str,
    file_type: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom solution slot and its generated file; fixed slots are rejected."""
    session = await get_session_or_404(db, session_id, user_id)

    if not file_type.startswith("sol_custom_"):
        raise HTTPException(400, "Можно удалять только кастомные решения")

    meta = dict(session.solution_meta or {})
    if file_type not in meta:
        raise HTTPException(404, f"Решение '{file_type}' не найдено")

    del meta[file_type]
    session.solution_meta = meta
    flag_modified(session, "solution_meta")

    await db.execute(
        delete(TaskGeneratedFile)
        .where(TaskGeneratedFile.session_id == session_id)
        .where(TaskGeneratedFile.file_type == file_type)
    )
    session.updated_at = now_utc()
    await db.commit()

    return {"session_id": session_id, "deleted": file_type, "solution_meta": meta}
