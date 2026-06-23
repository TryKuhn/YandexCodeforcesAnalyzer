"""POST /build-with-repair — build the package with AI auto-repair on failure."""
from fastapi import BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import ApproveFilesRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.build.repair import run_build_with_repair
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from app.database import get_db
from models.task.session import PipelineStage


@gpt_router.post("/build-with-repair")
async def build_with_repair(
    request: ApproveFilesRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Launch a background package build with AI auto-repair on failure."""
    session = await get_session_or_404(db, request.session_id, user_id)
    if not session.polygon_problem_id:
        raise HTTPException(400, "Задача ещё не создана в Polygon")

    session.stage = PipelineStage.BUILDING_PACKAGE
    session.progress = {"status": "building", "current_step": "Запуск сборки..."}
    session.updated_at = now_utc()
    await db.commit()

    background_tasks.add_task(run_build_with_repair, request.session_id)
    return {"status": "build_started", "session_id": request.session_id}
