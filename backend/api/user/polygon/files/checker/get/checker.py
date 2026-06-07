from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def get_checker(problem_id: int, user_id: int, db: AsyncSession):
    user = await get_user(user_id, db)
    return await polygon_call("problem.checker", {"problemId": str(problem_id)}, user)
