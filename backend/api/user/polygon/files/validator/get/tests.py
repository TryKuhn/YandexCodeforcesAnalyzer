"""Fetch the validator tests of a Polygon problem."""

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def get_validator_tests(problem_id: int, user_id: int, db: AsyncSession):
    """Return the problem's validator tests (problem.validatorTests)."""
    user = await get_user(user_id, db)
    return await polygon_call(
        "problem.validatorTests", {"problemId": str(problem_id)}, user
    )
