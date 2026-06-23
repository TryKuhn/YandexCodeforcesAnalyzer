"""POST /post-build-refine — task-scope AI refinement of an existing problem.

Kept as a dedicated URL for the current frontend; internally it is the task
branch of the chat modify executor, so edits also sync to Polygon.
"""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import PostBuildRefineRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.ai_file_helpers import get_all_file_contents
from api.user.gpt.services.chat import modify_executor
from api.user.gpt.services.chat.context_resolver import ResolvedContext
from api.user.gpt.services.sessions import get_session_or_404
from app.database import get_db
from models.task.session import PipelineStage


@gpt_router.post("/post-build-refine")
async def post_build_refine(
    request: PostBuildRefineRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run a task-scope AI refinement of an existing problem and sync to Polygon."""
    session = await get_session_or_404(db, request.session_id, user_id)

    if session.stage not in (PipelineStage.DONE, PipelineStage.FILES_REVIEW,
                             PipelineStage.FIXING_ERRORS):
        raise HTTPException(400, f"Доработка недоступна на этапе '{session.stage}'")

    files = await get_all_file_contents(db, session.id)
    if not files:
        raise HTTPException(400, "Нет файлов для доработки")

    resolved = ResolvedContext(scope="task", candidates=list(files.keys()))
    result = await modify_executor.execute(db, session, request.message, resolved)

    return {
        "session_id": session.id,
        "updated_files": result["updated_files"],
        "technical_data": await get_all_file_contents(db, session.id),
        "stage": session.stage,
    }
