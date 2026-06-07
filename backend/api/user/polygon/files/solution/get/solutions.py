from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call
from models.task.problem import PolygonProblem
from models.task.solution import PolygonSolution


async def get_solutions(problem_id: int, user_id: int, db: AsyncSession):
    user = await get_user(user_id, db)
    result = await polygon_call("problem.solutions", {"problemId": str(problem_id)}, user)

    if isinstance(result, list):
        cached_problem = (
            await db.execute(
                select(PolygonProblem).filter_by(user_id=user_id, polygon_id=problem_id)
            )
        ).scalars().first()

        if cached_problem:
            for sol in result:
                name = sol.get("name", "")
                existing = (
                    await db.execute(
                        select(PolygonSolution).filter_by(
                            problem_id=cached_problem.id, name=name
                        )
                    )
                ).scalars().first()

                if existing:
                    existing.source_type = sol.get("sourceType")
                    existing.tag = sol.get("tag")
                else:
                    db.add(PolygonSolution(
                        problem_id=cached_problem.id,
                        name=name,
                        content="",
                        source_type=sol.get("sourceType"),
                        tag=sol.get("tag"),
                        uploaded=True,
                    ))
            await db.commit()

    return result
