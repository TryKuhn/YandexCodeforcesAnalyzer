from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def get_packages(problem_id: int, user_id: int, db: AsyncSession):
    """List the problem's packages via problem.packages."""
    user = await get_user(user_id, db)
    return await polygon_call("problem.packages", {"problemId": str(problem_id)}, user)
