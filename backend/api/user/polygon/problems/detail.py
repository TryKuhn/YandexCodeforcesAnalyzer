from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.polygon.problem.get.info import get_problem_info
from api.user.polygon.problem.get.list import list_problems
from api.user.polygon.statement.get.setatement import get_statements
from app.database import get_db
from models.task.problem import PolygonProblem
from models.task.test_group import PolygonTestGroup

router = APIRouter()


@router.get("/{polygon_id}")
async def route_get_problem(
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

    if problem is None:
        # Try to populate cache from Polygon before giving up
        await list_problems(user_id=user_id, db=db)
        result = await db.execute(
            select(PolygonProblem).where(
                PolygonProblem.user_id == user_id,
                PolygonProblem.polygon_id == polygon_id,
            )
        )
        problem = result.scalars().first()

    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found")

    tg_count = (
        await db.execute(
            select(func.count()).where(PolygonTestGroup.problem_id == problem.id)
        )
    ).scalar()

    return {
        "id": problem.id,
        "polygon_id": problem.polygon_id,
        "name": problem.name,
        "owner": problem.owner,
        "deleted": problem.deleted,
        "favourite": problem.favourite,
        "access_type": problem.access_type,
        "revision": problem.revision,
        "working_copy_revision": problem.working_copy_revision,
        "latest_package": problem.latest_package,
        "modified": problem.modified,
        "input_file": problem.input_file,
        "output_file": problem.output_file,
        "interactive": problem.interactive,
        "well_formed": problem.well_formed,
        "time_limit": problem.time_limit,
        "memory_limit": problem.memory_limit,
        "list_fetched_at": problem.list_fetched_at,
        "info_fetched_at": problem.info_fetched_at,
        "enable_groups": tg_count > 0,
    }


@router.post("/{polygon_id}/sync")
async def route_sync_problem(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_problem_info(problem_id=polygon_id, user_id=user_id, db=db)
    await get_statements(problem_id=polygon_id, user_id=user_id, db=db)
    return {"ok": True}
