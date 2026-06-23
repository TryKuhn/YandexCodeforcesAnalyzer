from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call
from models.task.problem import PolygonProblem


async def get_problem_info(problem_id: int, user_id: int, db: AsyncSession):
    """Fetch problem.info from Polygon and refresh the cached PolygonProblem row.

    When the API returns a dict and a matching cached row exists, its limits and
    flags are updated and ``info_fetched_at`` is stamped before committing.
    """
    user = await get_user(user_id, db)
    info = await polygon_call("problem.info", {"problemId": str(problem_id)}, user)

    if isinstance(info, dict):
        result = await db.execute(
            select(PolygonProblem).filter_by(user_id=user_id, polygon_id=problem_id)
        )
        cached = result.scalars().first()
        if cached:
            cached.input_file = info.get("inputFile")
            cached.output_file = info.get("outputFile")
            cached.interactive = bool(info.get("interactive", False))
            cached.well_formed = bool(info.get("wellFormed", False))
            cached.time_limit = info.get("timeLimit")
            cached.memory_limit = info.get("memoryLimit")
            cached.info_fetched_at = datetime.utcnow()
            await db.commit()

    return info
