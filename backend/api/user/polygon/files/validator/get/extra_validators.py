"""Fetch the extra validators of a Polygon problem."""

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def get_extra_validators(problem_id: int, user_id: int, db: AsyncSession):
    """Return the problem's extra validators (problem.extraValidators)."""
    user = await get_user(user_id, db)
    return await polygon_call(
        "problem.extraValidators", {"problemId": str(problem_id)}, user
    )
