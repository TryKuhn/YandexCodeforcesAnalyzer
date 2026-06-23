"""POST /approve-files — start the full upload+build pipeline in the background."""
from fastapi import BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import ApproveFilesRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.ai_file_helpers import get_session_files
from api.user.gpt.services.build.pipeline import run_full_build
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from app.database import get_db
from models.task.session import PipelineStage


@gpt_router.post("/approve-files")
async def approve_files(
    request: ApproveFilesRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Validate the session and launch the full upload+build pipeline in the background."""
    session = await get_session_or_404(db, request.session_id, user_id)

    if session.stage not in (PipelineStage.FILES_REVIEW, PipelineStage.FAILED,
                             PipelineStage.FIXING_ERRORS):
        raise HTTPException(400, f"Нельзя запустить загрузку на этапе '{session.stage}'")

    if not await get_session_files(db, session.id):
        raise HTTPException(400, "Нет технических файлов для загрузки")

    session.stage = PipelineStage.UPLOADING
    session.progress = {"status": "uploading",
                        "current_step": "Запуск загрузки в Polygon..."}
    session.updated_at = now_utc()
    await db.commit()

    background_tasks.add_task(run_full_build, request.session_id)
    return {"status": "upload_started", "session_id": request.session_id}
