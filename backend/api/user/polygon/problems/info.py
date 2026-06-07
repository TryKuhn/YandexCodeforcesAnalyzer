from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import UpdateInfoRequest
from api.user.polygon.problem.get.info import get_problem_info
from api.user.polygon.problem.settings.update_info import update_info
from app.database import get_db
from models.task.problem import PolygonProblem

router = APIRouter()


@router.get("/{polygon_id}/info")
async def route_get_info(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PolygonProblem).where(
            PolygonProblem.user_id == user_id,
            PolygonProblem.polygon_id == polygon_id,
        )
    )
    problem = result.scalars().first()

    if problem and problem.info_fetched_at is not None:
        return {
            "inputFile": problem.input_file or "stdin",
            "outputFile": problem.output_file or "stdout",
            "interactive": problem.interactive,
            "timeLimit": problem.time_limit or 2000,
            "memoryLimit": problem.memory_limit or 256,
            "wellFormed": problem.well_formed,
        }

    # Fall back to Polygon API (first time or not cached)
    return await get_problem_info(problem_id=polygon_id, user_id=user_id, db=db)


@router.patch("/{polygon_id}/info")
async def route_update_info(
    polygon_id: int,
    body: UpdateInfoRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await update_info(
        problem_id=polygon_id,
        user_id=user_id,
        db=db,
        input_file_name=body.input_file,
        output_file_name=body.output_file,
        interactive=body.interactive,
        time_limit=body.time_limit,
        memory_limit=body.memory_limit,
    )
    return {"ok": True}
