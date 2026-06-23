"""GET /sessions — list the current user's AI task sessions."""
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.gpt.base_gpt import gpt_router
from app.database import get_db
from models.task.session import TaskSession


@gpt_router.get("/sessions")
async def list_sessions(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's sessions, most recently updated first."""
    result = await db.execute(
        select(TaskSession)
        .where(TaskSession.user_id == user_id)
        .order_by(TaskSession.updated_at.desc())
    )
    sessions = result.scalars().all()

    return [
        {
            "session_id": s.id,
            "stage": s.stage,
            "problem_type": s.problem_type,
            "name": (
                s.statement.get("name", "Без названия") if s.statement else "Черновик"
            ),
            "model": s.model,
            "polygon_problem_id": s.polygon_problem_id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in sessions
    ]
