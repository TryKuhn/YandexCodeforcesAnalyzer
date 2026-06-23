"""GET /upload-progress/{session_id} — pipeline progress + current artifacts."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.ai_file_helpers import get_all_file_contents
from api.user.gpt.services.sessions import get_session_or_404
from app.database import get_db


@gpt_router.get("/upload-progress/{session_id}")
async def get_upload_progress(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the session's pipeline progress alongside its current artifacts."""
    session = await get_session_or_404(db, session_id, user_id)
    progress = session.progress or {}

    return {
        "status": progress.get("status", "idle"),
        "stage": session.stage,
        "current_step": progress.get("current_step"),
        "error": progress.get("error"),
        "retries": progress.get("retries"),
        "upload_errors": session.upload_errors or {},
        "polygon_problem_id": session.polygon_problem_id,
        "technical_data": await get_all_file_contents(db, session_id),
        "problem_settings": session.problem_settings or {},
        "solution_meta": session.solution_meta or {},
        "examples": session.examples or [],
    }
