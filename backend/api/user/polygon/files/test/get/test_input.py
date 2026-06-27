"""Fetch the input for a test of a Polygon problem."""
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def get_test_input(
    problem_id: int, testset: str, test_index: int, user_id: int, db: AsyncSession
) -> str:
    """Return a test's input via ``problem.testInput`` (works for manual AND
    generated tests). The method returns PLAIN TEXT, which ``get_response`` wraps
    as ``{"message": ...}`` (even when the body is a bare scalar like ``"190"``)."""
    user = await get_user(user_id, db)
    res = await polygon_call(
        "problem.testInput",
        {"problemId": str(problem_id), "testset": testset, "testIndex": str(test_index)},
        user,
    )
    return res.get("message", "") if isinstance(res, dict) else str(res)
