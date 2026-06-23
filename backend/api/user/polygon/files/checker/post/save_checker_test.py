"""Save a checker test for a Polygon problem."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def save_checker_test(
    problem_id: int,
    test_index: int,
    test_input: str,
    test_output: str,
    test_answer: str,
    test_verdict: str,
    user_id: int,
    db: AsyncSession,
    check_existing: Optional[bool] = None,
):
    """Add or edit a checker test by index (problem.saveCheckerTest)."""
    user = await get_user(user_id, db)
    params: dict = {
        "problemId": str(problem_id),
        "testIndex": str(test_index),
        "testInput": test_input,
        "testOutput": test_output,
        "testAnswer": test_answer,
        "testVerdict": test_verdict,
    }
    if check_existing is not None:
        params["checkExisting"] = "true" if check_existing else "false"
    return await polygon_call("problem.saveCheckerTest", params, user)
