from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def view_tags(problem_id: int, user_id: int, db: AsyncSession):
    """Return the problem's tags via problem.viewTags."""
    user = await get_user(user_id, db)
    return await polygon_call("problem.viewTags", {"problemId": str(problem_id)}, user)
