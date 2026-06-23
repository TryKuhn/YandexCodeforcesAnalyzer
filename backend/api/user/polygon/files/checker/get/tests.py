"""Fetch the checker tests for a Polygon problem."""

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def get_checker_tests(problem_id: int, user_id: int, db: AsyncSession):
    """Return the problem's checker tests (problem.checkerTests)."""
    user = await get_user(user_id, db)
    return await polygon_call(
        "problem.checkerTests", {"problemId": str(problem_id)}, user
    )
