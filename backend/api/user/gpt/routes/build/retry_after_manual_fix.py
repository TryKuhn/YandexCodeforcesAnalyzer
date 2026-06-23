"""POST /retry-after-manual-fix — rerun the build after manual edits.

The full pipeline is idempotent (it re-pushes every file and rebuilds), so a
retry simply runs it again with the current session state.
"""
from fastapi import BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import ApproveFilesRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.build.pipeline import run_full_build
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from app.database import get_db
from models.task.session import PipelineStage


@gpt_router.post("/retry-after-manual-fix")
async def retry_after_manual_fix_endpoint(
    request: ApproveFilesRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clear upload errors and rerun the idempotent full pipeline after a manual fix."""
    session = await get_session_or_404(db, request.session_id, user_id)

    if session.stage not in (PipelineStage.FIXING_ERRORS, PipelineStage.FAILED,
                             PipelineStage.DONE):
        raise HTTPException(400, f"Повтор загрузки недоступен на этапе '{session.stage}'")

    session.stage = PipelineStage.UPLOADING
    session.progress = {"status": "uploading",
                        "current_step": "Повторная загрузка в Polygon..."}
    session.upload_errors = {}
    session.updated_at = now_utc()
    await db.commit()

    background_tasks.add_task(run_full_build, request.session_id)
    return {"status": "retry_started", "session_id": request.session_id}
