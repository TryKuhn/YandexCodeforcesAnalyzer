"""Save a validator test for a Polygon problem."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def save_validator_test(
    problem_id: int,
    test_index: int,
    test_input: str,
    test_verdict: str,
    user_id: int,
    db: AsyncSession,
    check_existing: Optional[bool] = None,
    test_group: Optional[str] = None,
    testset: Optional[str] = None,
):
    """Add or edit a validator test by index (problem.saveValidatorTest)."""
    user = await get_user(user_id, db)
    params: dict = {
        "problemId": str(problem_id),
        "testIndex": str(test_index),
        "testInput": test_input,
        "testVerdict": test_verdict,
    }
    if check_existing is not None:
        params["checkExisting"] = "true" if check_existing else "false"
    if test_group:
        params["testGroup"] = test_group
    if testset:
        params["testset"] = testset
    return await polygon_call("problem.saveValidatorTest", params, user)
