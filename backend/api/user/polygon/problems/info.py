"""Routes for reading and updating a problem's general info (limits, files, interactivity)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import UpdateInfoRequest
from api.user.polygon.cache import refresh_problem_info
from api.user.polygon.methods import update_info
from app.database import get_db
from models.task.problem import PolygonProblem

router = APIRouter()


@router.get("/{polygon_id}/info")
async def route_get_info(
    polygon_id: int,
    refresh: bool = False,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return cached problem info; hit Polygon when not cached yet or ``refresh=true``."""
    if not refresh:
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

    return await refresh_problem_info(polygon_id, user_id, db)


@router.patch("/{polygon_id}/info")
async def route_update_info(
    polygon_id: int,
    body: UpdateInfoRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the given info fields on Polygon, then refresh the cached row.

    Empty file names and zero limits mean "not set" (as before) and are skipped.
    """
    await update_info(
        polygon_id,
        user_id,
        db,
        input_file=body.input_file or None,
        output_file=body.output_file or None,
        interactive=body.interactive,
        well_formed=body.well_formed,
        skip_duplicated_tests_validation=body.skip_duplicated_tests_validation,
        time_limit=body.time_limit or None,
        memory_limit=body.memory_limit or None,
    )
    await refresh_problem_info(polygon_id, user_id, db)
    return {"ok": True}
