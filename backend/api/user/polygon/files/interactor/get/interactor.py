"""Fetch the configured interactor for a Polygon problem."""

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def get_interactor(problem_id: int, user_id: int, db: AsyncSession):
    """Return the problem's interactor (problem.interactor)."""
    user = await get_user(user_id, db)
    return await polygon_call("problem.interactor", {"problemId": str(problem_id)}, user)
