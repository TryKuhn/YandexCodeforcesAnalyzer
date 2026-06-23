"""Fetch the jury answer for a test of a Polygon problem."""

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def get_test_answer(
    problem_id: int, testset: str, test_index: int, user_id: int, db: AsyncSession
):
    """Return the test's jury answer (problem.testAnswer)."""
    user = await get_user(user_id, db)
    result = await polygon_call(
        "problem.testAnswer",
        {"problemId": str(problem_id), "testset": testset, "testIndex": str(test_index)},
        user,
    )
    return result.get("message", "") if isinstance(result, dict) else str(result)
