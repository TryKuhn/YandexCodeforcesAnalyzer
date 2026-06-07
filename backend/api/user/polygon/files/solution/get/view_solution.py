from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def view_solution(problem_id: int, name: str, user_id: int, db: AsyncSession):
    user = await get_user(user_id, db)
    result = await polygon_call(
        "problem.viewSolution",
        {"problemId": str(problem_id), "name": name},
        user,
    )
    return result.get("message", "") if isinstance(result, dict) else str(result)
